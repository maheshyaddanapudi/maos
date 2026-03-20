"""A2A agent discovery."""

import asyncio
from urllib.parse import urljoin

import httpx
import structlog

from maos.a2a.models import AgentCard, DiscoveredAgent, HostIndex
from maos.config.models import A2AConfig, A2AImportPolicy

logger = structlog.get_logger()


class A2ADiscovery:
    """Discover external A2A agents from seed URLs."""

    def __init__(self, http_client: httpx.AsyncClient | None = None):
        """
        Initialize A2A discovery.

        Args:
            http_client: HTTP client to use. Creates one if not provided.
        """
        self._http_client = http_client
        self._owns_client = http_client is None

    async def discover(self, config: A2AConfig) -> list[DiscoveredAgent]:
        """
        Discover agents from seed URLs.

        Args:
            config: A2A configuration.

        Returns:
            List of discovered agents after applying import policy.
        """
        if not config.import_policy.enabled:
            logger.info("a2a_discovery_disabled")
            return []

        if not config.discovery.seeds:
            logger.info("no_a2a_seeds_configured")
            return []

        # Create client if needed
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=config.discovery.timeout_seconds
            )

        try:
            # Discover agents from all seeds
            if config.discovery.parallel_discovery:
                discovered = await self._discover_parallel(config)
            else:
                discovered = await self._discover_sequential(config)

            # Apply import policy
            filtered = self._apply_policy(discovered, config.import_policy)

            logger.info(
                "a2a_discovery_complete",
                total_discovered=len(discovered),
                after_policy=len(filtered)
            )

            return filtered

        finally:
            if self._owns_client and self._http_client:
                await self._http_client.aclose()
                self._http_client = None

    async def _discover_parallel(self, config: A2AConfig) -> list[DiscoveredAgent]:
        """Discover agents from all seeds in parallel."""
        tasks = [
            self._discover_from_seed(seed, config)
            for seed in config.discovery.seeds
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        discovered = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("seed_discovery_failed", error=str(result))
            else:
                discovered.extend(result)

        return discovered

    async def _discover_sequential(self, config: A2AConfig) -> list[DiscoveredAgent]:
        """Discover agents from all seeds sequentially."""
        discovered = []
        for seed in config.discovery.seeds:
            try:
                agents = await self._discover_from_seed(seed, config)
                discovered.extend(agents)
            except Exception as e:
                logger.warning("seed_discovery_failed", seed=seed, error=str(e))
        return discovered

    async def _discover_from_seed(
        self,
        seed_url: str,
        config: A2AConfig
    ) -> list[DiscoveredAgent]:
        """Discover agents from a single seed URL."""
        discovered = []

        # Try host index first
        host_index = await self._fetch_host_index(seed_url, config)
        if host_index:
            for agent_info in host_index.agents:
                card_path = agent_info.get(
                    "agent_card_path",
                    f"{agent_info['path']}/.well-known/agent.json"
                )
                card_url = urljoin(seed_url, card_path)
                agent = await self._fetch_and_create_agent(card_url, config)
                if agent:
                    discovered.append(agent)
            return discovered

        # Try well-known paths
        for wk_path in config.discovery.well_known_paths:
            card_url = urljoin(seed_url, wk_path)
            agent = await self._fetch_and_create_agent(card_url, config)
            if agent:
                discovered.append(agent)
                break  # Found agent card

        return discovered

    async def _fetch_host_index(
        self,
        base_url: str,
        config: A2AConfig
    ) -> HostIndex | None:
        """Fetch host index from a multi-agent host."""
        index_url = urljoin(base_url, config.discovery.host_index_path)
        try:
            response = await self._http_client.get(index_url)
            if response.status_code == 200:
                return HostIndex.model_validate(response.json())
        except Exception as e:
            logger.debug("host_index_not_found", url=index_url, error=str(e))
        return None

    async def _fetch_and_create_agent(
        self,
        card_url: str,
        config: A2AConfig
    ) -> DiscoveredAgent | None:
        """Fetch agent card and create DiscoveredAgent."""
        card = await self._fetch_agent_card(card_url)
        if card is None:
            return None

        # Determine endpoint
        endpoint = card.endpoint
        if not endpoint:
            # Derive from card URL
            endpoint = card_url.rsplit("/.well-known", 1)[0]

        return DiscoveredAgent(
            card=card,
            source_url=card_url,
            endpoint=endpoint,
            import_mode="node" if config.import_policy.mode == "langgraph_nodes" else "tool"
        )

    async def _fetch_agent_card(self, url: str) -> AgentCard | None:
        """Fetch and parse an agent card."""
        try:
            response = await self._http_client.get(url)
            if response.status_code == 200:
                card = AgentCard.model_validate(response.json())
                card.url = url
                logger.debug("fetched_agent_card", name=card.name, url=url)
                return card
        except Exception as e:
            logger.warning("failed_to_fetch_agent_card", url=url, error=str(e))
        return None

    def _apply_policy(
        self,
        agents: list[DiscoveredAgent],
        policy: A2AImportPolicy
    ) -> list[DiscoveredAgent]:
        """Apply import policy filters to discovered agents."""
        filtered = agents

        # Filter by tags
        if policy.include_tags:
            filtered = [
                a for a in filtered
                if any(t in a.card.all_tags for t in policy.include_tags)
            ]

        if policy.exclude_tags:
            filtered = [
                a for a in filtered
                if not any(t in a.card.all_tags for t in policy.exclude_tags)
            ]

        # Filter by names
        if policy.include_names:
            filtered = [
                a for a in filtered
                if a.card.name in policy.include_names
            ]

        if policy.exclude_names:
            filtered = [
                a for a in filtered
                if a.card.name not in policy.exclude_names
            ]

        # Apply limit
        return filtered[:policy.max_agents]

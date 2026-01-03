"""
MAOS A2A Discovery.

Discovers external A2A agents from seed URLs.
"""

import asyncio
from typing import Any

import httpx
import structlog

from maos.a2a.models import AgentCard, DiscoveredAgent
from maos.config.models import A2AConfig, A2AImportPolicy

log = structlog.get_logger()


class A2ADiscovery:
    """Discover and import external A2A agents."""

    def __init__(self, http_client: httpx.AsyncClient | None = None):
        self._http_client = http_client
        self._owns_client = http_client is None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=10.0)
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client if owned."""
        if self._owns_client and self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def discover(self, config: A2AConfig) -> list[DiscoveredAgent]:
        """Discover agents from seed URLs.

        Args:
            config: A2A configuration

        Returns:
            List of discovered agents
        """
        if not config.import_policy.enabled:
            log.info("a2a_discovery_disabled")
            return []

        seeds = config.discovery.seeds
        if not seeds:
            log.info("no_a2a_seeds_configured")
            return []

        log.info("discovering_a2a_agents", seed_count=len(seeds))

        discovered: list[DiscoveredAgent] = []

        # Process seeds
        if config.discovery.parallel_discovery:
            tasks = [
                self._process_seed(seed, config.discovery)
                for seed in seeds
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    discovered.extend(result)
                elif isinstance(result, Exception):
                    log.warning("seed_discovery_failed", error=str(result))
        else:
            for seed in seeds:
                try:
                    agents = await self._process_seed(seed, config.discovery)
                    discovered.extend(agents)
                except Exception as e:
                    log.warning("seed_discovery_failed", seed=seed, error=str(e))

        # Apply import policy
        filtered = self._apply_policy(discovered, config.import_policy)

        log.info(
            "a2a_discovery_complete",
            discovered=len(discovered),
            imported=len(filtered),
        )

        return filtered

    async def _process_seed(
        self,
        seed_url: str,
        discovery_config,
    ) -> list[DiscoveredAgent]:
        """Process a single seed URL."""
        seed_url = seed_url.rstrip("/")

        # Try to fetch host index first
        host_index = await self._fetch_host_index(
            seed_url,
            discovery_config.host_index_path,
            discovery_config.timeout_seconds,
        )

        if host_index:
            # Multi-agent host
            return await self._process_host_index(
                seed_url,
                host_index,
                discovery_config,
            )

        # Try individual agent
        for path in discovery_config.well_known_paths:
            card = await self._fetch_agent_card(
                f"{seed_url}{path}",
                discovery_config.timeout_seconds,
            )
            if card:
                endpoint = card.endpoint or seed_url
                return [DiscoveredAgent(
                    card=card,
                    source_url=seed_url,
                    endpoint=endpoint,
                )]

        log.warning("no_agent_found_at_seed", seed=seed_url)
        return []

    async def _fetch_host_index(
        self,
        base_url: str,
        path: str,
        timeout: int,
    ) -> dict[str, Any] | None:
        """Fetch multi-agent host index."""
        try:
            client = await self._get_client()
            url = f"{base_url}{path}"

            response = await client.get(url, timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                if "agents" in data:
                    log.debug("host_index_found", url=url)
                    return data
        except Exception as e:
            log.debug("host_index_not_found", url=base_url, error=str(e))

        return None

    async def _fetch_agent_card(
        self,
        url: str,
        timeout: int,
    ) -> AgentCard | None:
        """Fetch individual Agent Card."""
        try:
            client = await self._get_client()

            response = await client.get(url, timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                if "name" in data:
                    log.debug("agent_card_found", url=url, name=data.get("name"))
                    return AgentCard.from_dict(data, url)
        except Exception as e:
            log.debug("agent_card_fetch_failed", url=url, error=str(e))

        return None

    async def _process_host_index(
        self,
        base_url: str,
        host_index: dict[str, Any],
        discovery_config,
    ) -> list[DiscoveredAgent]:
        """Process agents from host index."""
        agents_data = host_index.get("agents", [])
        discovered: list[DiscoveredAgent] = []

        for agent_info in agents_data:
            agent_path = agent_info.get("path", "")
            card_path = agent_info.get("agent_card_path") or f"{agent_path}/.well-known/agent.json"

            card = await self._fetch_agent_card(
                f"{base_url}{card_path}",
                discovery_config.timeout_seconds,
            )

            if card:
                endpoint = card.endpoint or f"{base_url}{agent_path}"
                discovered.append(DiscoveredAgent(
                    card=card,
                    source_url=base_url,
                    endpoint=endpoint,
                ))

        return discovered

    def _apply_policy(
        self,
        agents: list[DiscoveredAgent],
        policy: A2AImportPolicy,
    ) -> list[DiscoveredAgent]:
        """Apply import policy filters."""
        if not agents:
            return []

        filtered = agents

        # Filter by include_tags
        if policy.include_tags:
            filtered = [
                a for a in filtered
                if any(t in a.card.all_tags for t in policy.include_tags)
            ]

        # Filter by exclude_tags
        if policy.exclude_tags:
            filtered = [
                a for a in filtered
                if not any(t in a.card.all_tags for t in policy.exclude_tags)
            ]

        # Filter by include_names
        if policy.include_names:
            filtered = [
                a for a in filtered
                if a.card.name in policy.include_names
            ]

        # Filter by exclude_names
        if policy.exclude_names:
            filtered = [
                a for a in filtered
                if a.card.name not in policy.exclude_names
            ]

        # Apply max_agents limit
        filtered = filtered[:policy.max_agents]

        # Set import mode
        for agent in filtered:
            agent.import_mode = "node" if policy.mode.value == "langgraph_nodes" else "tool"

        return filtered

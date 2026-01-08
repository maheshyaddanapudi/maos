"""Conversation history endpoints.

This module provides endpoints for listing and retrieving conversation history:
- GET /conversations - List all conversations with metadata
- GET /conversations/{thread_id} - Get full conversation state
- GET /conversations/{thread_id}/messages - Get just the messages
- DELETE /conversations/{thread_id} - Delete a conversation

These endpoints work with any checkpointer (memory, SQLite, PostgreSQL)
but persistent storage (SQLite/Postgres) is required for data to survive restarts.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/conversations", tags=["conversations"])


# =============================================================================
# Response Models
# =============================================================================

class ConversationSummary(BaseModel):
    """Summary info for a conversation."""
    thread_id: str
    message_count: int = 0
    last_message_preview: str = ""
    last_update: Optional[str] = None
    status: str = "idle"  # idle, interrupted, error


class ConversationMessage(BaseModel):
    """A message in a conversation."""
    role: str
    content: str
    name: Optional[str] = None


class ConversationDetail(BaseModel):
    """Full conversation details."""
    thread_id: str
    messages: List[ConversationMessage]
    message_count: int
    is_interrupted: bool = False
    interrupt_prompt: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConversationListResponse(BaseModel):
    """Response for listing conversations."""
    conversations: List[ConversationSummary]
    total: int
    limit: int
    offset: int


class MessageListResponse(BaseModel):
    """Response for listing messages."""
    thread_id: str
    messages: List[ConversationMessage]
    total: int


# =============================================================================
# Dependency
# =============================================================================

def get_app_context() -> Dict[str, Any]:
    """Get application context - to be overridden by dependency injection."""
    return {}


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    context: Dict[str, Any] = Depends(get_app_context)
) -> ConversationListResponse:
    """
    List all conversations with summary information.

    Returns conversations ordered by last update (most recent first).
    Includes thread_id, message count, and a preview of the last message.

    Note: With in-memory checkpointer, this list resets on server restart.
    Use SQLite or PostgreSQL checkpointer for persistence.
    """
    conversation_store = context.get("conversation_store")
    graph = context.get("graph")

    if not conversation_store and not graph:
        raise HTTPException(status_code=503, detail="Conversation store not initialized")

    conversations = []

    # If we have a ConversationStore, use it
    if conversation_store:
        try:
            threads = await conversation_store.list_threads(limit=limit, offset=offset)
            for thread_info in threads:
                conversations.append(ConversationSummary(
                    thread_id=thread_info.get("thread_id", ""),
                    message_count=thread_info.get("message_count", 0),
                    last_message_preview=thread_info.get("last_message_preview", ""),
                    last_update=thread_info.get("last_update"),
                ))
        except Exception as e:
            logger.error("list_conversations_error", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    # Fallback: Try to get threads from graph checkpointer directly
    elif graph:
        checkpointer = getattr(graph, 'checkpointer', None)
        if checkpointer:
            storage = getattr(checkpointer, 'storage', {})
            thread_ids = list(storage.keys())[offset:offset + limit]

            for thread_id in thread_ids:
                try:
                    config = {"configurable": {"thread_id": thread_id}}
                    state = await graph.aget_state(config)

                    if state and state.values:
                        messages = state.values.get("messages", [])
                        last_preview = ""
                        if messages:
                            last_msg = messages[-1]
                            if hasattr(last_msg, "content"):
                                last_preview = str(last_msg.content)[:100]
                            elif isinstance(last_msg, dict):
                                last_preview = str(last_msg.get("content", ""))[:100]

                        status = "interrupted" if state.next else "idle"

                        conversations.append(ConversationSummary(
                            thread_id=thread_id,
                            message_count=len(messages),
                            last_message_preview=last_preview,
                            status=status,
                        ))
                except Exception as e:
                    logger.warning("get_thread_info_error", thread_id=thread_id, error=str(e))

    return ConversationListResponse(
        conversations=conversations,
        total=len(conversations),
        limit=limit,
        offset=offset,
    )


@router.get("/{thread_id}", response_model=ConversationDetail)
async def get_conversation(
    thread_id: str,
    context: Dict[str, Any] = Depends(get_app_context)
) -> ConversationDetail:
    """
    Get full conversation details including all messages and state.

    Returns the complete message history and current state (whether
    the conversation is waiting for user input, etc.).
    """
    graph = context.get("graph")

    if not graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    config = {"configurable": {"thread_id": thread_id}}

    try:
        state = await graph.aget_state(config)

        if not state or state.values is None:
            raise HTTPException(status_code=404, detail=f"Conversation {thread_id} not found")

        # Extract messages
        raw_messages = state.values.get("messages", [])
        messages = []
        for msg in raw_messages:
            if hasattr(msg, "type") and hasattr(msg, "content"):
                role = "assistant" if msg.type == "ai" else msg.type
                if role == "human":
                    role = "user"
                messages.append(ConversationMessage(
                    role=role,
                    content=str(msg.content),
                    name=getattr(msg, "name", None),
                ))
            elif isinstance(msg, dict):
                messages.append(ConversationMessage(
                    role=msg.get("role", "unknown"),
                    content=msg.get("content", ""),
                    name=msg.get("name"),
                ))

        # Check if interrupted
        is_interrupted = state.next is not None
        interrupt_prompt = None

        if is_interrupted:
            tasks = getattr(state, 'tasks', [])
            if tasks and hasattr(tasks[0], 'interrupts') and tasks[0].interrupts:
                interrupt_value = tasks[0].interrupts[0].value
                if isinstance(interrupt_value, dict):
                    interrupt_prompt = interrupt_value.get("prompt")

        return ConversationDetail(
            thread_id=thread_id,
            messages=messages,
            message_count=len(messages),
            is_interrupted=is_interrupted,
            interrupt_prompt=interrupt_prompt,
            metadata=state.values.get("metadata", {}),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_conversation_error", thread_id=thread_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{thread_id}/messages", response_model=MessageListResponse)
async def get_conversation_messages(
    thread_id: str,
    context: Dict[str, Any] = Depends(get_app_context)
) -> MessageListResponse:
    """
    Get just the messages for a conversation.

    This is a lighter-weight endpoint when you only need the message
    history without the full state information.
    """
    conversation = await get_conversation(thread_id, context)

    return MessageListResponse(
        thread_id=thread_id,
        messages=conversation.messages,
        total=conversation.message_count,
    )


@router.delete("/{thread_id}")
async def delete_conversation(
    thread_id: str,
    context: Dict[str, Any] = Depends(get_app_context)
) -> Dict[str, Any]:
    """
    Delete a conversation and all its history.

    This permanently removes the conversation from storage.
    With in-memory checkpointer, this is equivalent to clearing the thread.
    With SQLite/Postgres, this removes the records from the database.
    """
    conversation_store = context.get("conversation_store")
    graph = context.get("graph")

    if not conversation_store and not graph:
        raise HTTPException(status_code=503, detail="Conversation store not initialized")

    try:
        deleted = False

        if conversation_store:
            deleted = await conversation_store.delete_thread(thread_id)

        elif graph:
            checkpointer = getattr(graph, 'checkpointer', None)
            if checkpointer:
                storage = getattr(checkpointer, 'storage', {})
                if thread_id in storage:
                    del storage[thread_id]
                    deleted = True

        if deleted:
            logger.info("conversation_deleted", thread_id=thread_id)
            return {"deleted": True, "thread_id": thread_id}
        else:
            raise HTTPException(status_code=404, detail=f"Conversation {thread_id} not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_conversation_error", thread_id=thread_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{thread_id}/status")
async def get_conversation_status(
    thread_id: str,
    context: Dict[str, Any] = Depends(get_app_context)
) -> Dict[str, Any]:
    """
    Get the current status of a conversation.

    Quick endpoint to check if a conversation exists and whether
    it's waiting for user input (interrupted).
    """
    graph = context.get("graph")

    if not graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    config = {"configurable": {"thread_id": thread_id}}

    try:
        state = await graph.aget_state(config)

        if not state or state.values is None:
            return {
                "thread_id": thread_id,
                "exists": False,
                "status": "not_found",
            }

        is_interrupted = state.next is not None
        status = "interrupted" if is_interrupted else "idle"

        return {
            "thread_id": thread_id,
            "exists": True,
            "status": status,
            "message_count": len(state.values.get("messages", [])),
            "next_node": list(state.next) if state.next else None,
        }

    except Exception as e:
        logger.error("get_status_error", thread_id=thread_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

"""
Session Manager Lambda - Context Persistence
Gestiona contexto de conversación y persistencia de sesiones.

Operations:
- /save-conversation: Guardar turno de conversación en DynamoDB (PutItem con TTL 90 días)
- /retrieve-context: Recuperar últimas 5 conversaciones (Query, newest first)
- /reset-context: Limpiar contexto de conversación (BatchWrite delete)

DynamoDB Table: financial-assistant-sessions
- PK: session_id (String), SK: timestamp (Number)
- TTL: ttl attribute (90 días)

Requirements: 8.1, 8.2
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

# Structured JSON logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
SESSIONS_TABLE = os.environ.get("SESSIONS_TABLE", "financial-assistant-sessions")

# DynamoDB resource
dynamodb = boto3.resource("dynamodb")
sessions_table = dynamodb.Table(SESSIONS_TABLE)

# Constants
TTL_DAYS = 90
CONTEXT_LIMIT = 5  # Retrieve last 5 conversations
BATCH_DELETE_MAX = 25  # DynamoDB BatchWriteItem limit


def log_structured(level: str, message: str, **kwargs):
    """Emit structured JSON log entry."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        "service": "session-manager",
        **kwargs,
    }
    if level == "ERROR":
        logger.error(json.dumps(entry, default=str))
    elif level == "WARNING":
        logger.warning(json.dumps(entry, default=str))
    else:
        logger.info(json.dumps(entry, default=str))


# ─────────────────────────────────────────────────────────────────────────────
# Operations
# ─────────────────────────────────────────────────────────────────────────────


def save_conversation(properties: list) -> dict:
    """
    Save a conversation turn to DynamoDB with TTL of 90 days.

    Expects properties array from Bedrock Agent requestBody format:
    [
        {"name": "session_id", "value": "..."},
        {"name": "client_id", "value": "..."},
        {"name": "message", "value": "..."},
        {"name": "response", "value": "..."},
        {"name": "action_groups_invoked", "value": "..."},
    ]
    """
    # Parse properties array into dict
    props = {p["name"]: p["value"] for p in properties}

    session_id = props.get("session_id", "").strip()
    client_id = props.get("client_id", "").strip()
    message = props.get("message", "")
    response = props.get("response", "")
    action_groups_invoked = props.get("action_groups_invoked", "[]")

    if not session_id:
        log_structured("WARNING", "Missing session_id in save_conversation")
        return {"error": "El parámetro session_id es requerido."}

    if not client_id:
        log_structured("WARNING", "Missing client_id in save_conversation")
        return {"error": "El parámetro client_id es requerido."}

    # Generate timestamp (sort key) and TTL
    now = int(time.time())
    ttl_value = now + (TTL_DAYS * 24 * 60 * 60)

    # Parse action_groups_invoked if it's a string
    if isinstance(action_groups_invoked, str):
        try:
            action_groups_invoked = json.loads(action_groups_invoked)
        except (json.JSONDecodeError, TypeError):
            action_groups_invoked = []

    # Build DynamoDB item
    item = {
        "session_id": session_id,
        "timestamp": now,
        "client_id": client_id,
        "message": message,
        "response": response,
        "action_groups_invoked": action_groups_invoked,
        "guardrail_triggered": False,
        "ttl": ttl_value,
    }

    try:
        sessions_table.put_item(Item=item)
        log_structured(
            "INFO", "Conversation saved",
            session_id=session_id, client_id=client_id, timestamp=now,
        )
    except Exception as e:
        # Non-blocking: log error but continue (Requirement 6.6)
        log_structured(
            "ERROR", "Failed to save conversation (non-blocking)",
            session_id=session_id, error=str(e),
        )

    return {
        "success": True,
        "timestamp": datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def retrieve_context(session_id: str) -> dict:
    """
    Retrieve the last 5 conversations for a session, newest first.

    Uses Query with ScanIndexForward=False and Limit=5.
    """
    if not session_id.strip():
        log_structured("WARNING", "Missing session_id in retrieve_context")
        return {"error": "El parámetro session_id es requerido."}

    try:
        response = sessions_table.query(
            KeyConditionExpression=Key("session_id").eq(session_id),
            ScanIndexForward=False,  # Newest first
            Limit=CONTEXT_LIMIT,
        )

        items = response.get("Items", [])

        conversation_history = [
            {
                "timestamp": datetime.fromtimestamp(
                    int(item["timestamp"]), tz=timezone.utc
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "message": item.get("message", ""),
                "response": item.get("response", ""),
            }
            for item in items
        ]

        log_structured(
            "INFO", "Context retrieved",
            session_id=session_id, turns_found=len(conversation_history),
        )

        return {
            "conversation_history": conversation_history,
            "total_turns": len(conversation_history),
        }

    except Exception as e:
        log_structured(
            "ERROR", "Failed to retrieve context",
            session_id=session_id, error=str(e),
        )
        return {
            "conversation_history": [],
            "total_turns": 0,
        }


def reset_context(session_id: str) -> dict:
    """
    Delete all conversation items for a session.

    Queries all items by session_id, then uses BatchWriteItem to delete them
    in batches of 25 (DynamoDB limit).
    """
    if not session_id.strip():
        log_structured("WARNING", "Missing session_id in reset_context")
        return {"error": "El parámetro session_id es requerido."}

    try:
        # Query all items for this session
        items_to_delete = []
        response = sessions_table.query(
            KeyConditionExpression=Key("session_id").eq(session_id),
            ProjectionExpression="session_id, #ts",
            ExpressionAttributeNames={"#ts": "timestamp"},
        )
        items_to_delete.extend(response.get("Items", []))

        # Handle pagination
        while "LastEvaluatedKey" in response:
            response = sessions_table.query(
                KeyConditionExpression=Key("session_id").eq(session_id),
                ProjectionExpression="session_id, #ts",
                ExpressionAttributeNames={"#ts": "timestamp"},
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items_to_delete.extend(response.get("Items", []))

        if not items_to_delete:
            log_structured("INFO", "No items to delete", session_id=session_id)
            return {
                "success": True,
                "message": "No hay contexto de conversación para reiniciar.",
            }

        # BatchWrite delete in batches of 25
        deleted_count = 0
        for i in range(0, len(items_to_delete), BATCH_DELETE_MAX):
            batch = items_to_delete[i : i + BATCH_DELETE_MAX]
            with sessions_table.batch_writer() as writer:
                for item in batch:
                    writer.delete_item(
                        Key={
                            "session_id": item["session_id"],
                            "timestamp": item["timestamp"],
                        }
                    )
                    deleted_count += 1

        log_structured(
            "INFO", "Context reset",
            session_id=session_id, items_deleted=deleted_count,
        )

        return {
            "success": True,
            "message": "Contexto de conversación reiniciado exitosamente.",
        }

    except Exception as e:
        log_structured(
            "ERROR", "Failed to reset context",
            session_id=session_id, error=str(e),
        )
        return {
            "success": False,
            "message": f"Error al reiniciar contexto: {str(e)}",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Bedrock Agent Response Helpers
# ─────────────────────────────────────────────────────────────────────────────


def build_response(event: dict, status_code: int, body: dict) -> dict:
    """Build Bedrock Agent response format."""
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup", "manage-session"),
            "apiPath": event.get("apiPath", ""),
            "httpMethod": event.get("httpMethod", "POST"),
            "httpStatusCode": status_code,
            "responseBody": {
                "application/json": {
                    "body": json.dumps(body, default=str)
                }
            },
        },
    }


def build_error_response(event: dict, status_code: int, error_message: str) -> dict:
    """Build error response in Bedrock Agent format."""
    return build_response(event, status_code, {"error": error_message})


# ─────────────────────────────────────────────────────────────────────────────
# Lambda Handler
# ─────────────────────────────────────────────────────────────────────────────


def handler(event, context):
    """Bedrock Agent Action Group handler for session management."""
    start_time = datetime.now(timezone.utc)

    log_structured("INFO", "Session manager request received", event=event)

    # Extract from Bedrock Agent event
    api_path = event.get("apiPath", "")
    parameters = {p["name"]: p["value"] for p in event.get("parameters", [])}

    log_structured("INFO", "Processing request", api_path=api_path)

    if api_path == "/save-conversation":
        # Extract request body (POST with body) - Bedrock Agent format
        request_body = event.get("requestBody", {})
        body_content = request_body.get("content", {})
        json_body = body_content.get("application/json", {})
        properties = json_body.get("properties", [])

        result = save_conversation(properties)

    elif api_path == "/retrieve-context":
        session_id = parameters.get("session_id", "")
        result = retrieve_context(session_id)

    elif api_path == "/reset-context":
        session_id = parameters.get("session_id", "")
        result = reset_context(session_id)

    else:
        log_structured("WARNING", "Unknown api_path", api_path=api_path)
        return build_error_response(event, 400, f"Ruta no reconocida: {api_path}")

    # Check if result contains an error
    if "error" in result:
        return build_error_response(event, 400, result["error"])

    # Log latency
    elapsed_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
    log_structured(
        "INFO", "Session manager request completed",
        api_path=api_path, latency_ms=round(elapsed_ms, 2),
    )

    return build_response(event, 200, result)

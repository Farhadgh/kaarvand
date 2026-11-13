"""SQLAlchemy model registry.

Import order matters only for metadata completeness; relationships are resolved
by name so cross module references are fine.
"""

from app.db.models.agents import Agent, AgentTask, AgentTool, AgentWorkflow
from app.db.models.apps import AppCatalog
from app.db.models.audit import AuditLog
from app.db.models.auth import AppSetting, LoginAttempt, OtpCode, UserMfa, UserSession
from app.db.models.billing import FeatureFlag, Payment, Plan, Wallet, WalletTransaction
from app.db.models.conversations import Conversation, Message
from app.db.models.core import ApiKey, Membership, Organization, User
from app.db.models.i18n import Translation
from app.db.models.inbound import InboundChannel, InboundEvent
from app.db.models.knowledge import Chunk, Document, KnowledgeBase
from app.db.models.llm_models import CapabilityRule, Model, PriceHistory
from app.db.models.prompts import Prompt, PromptExample, PromptVersion
from app.db.models.providers import Provider, ProviderAdapter
from app.db.models.runs import Run, TraceSpan
from app.db.models.tools import Device, DeviceTool, McpServer, Tool
from app.db.models.usage import ToolInvocation, UsageLedger

__all__ = [
    "Agent",
    "AgentTask",
    "AgentTool",
    "AgentWorkflow",
    "ApiKey",
    "AppCatalog",
    "AppSetting",
    "AuditLog",
    "CapabilityRule",
    "Chunk",
    "Conversation",
    "Device",
    "DeviceTool",
    "Document",
    "FeatureFlag",
    "InboundChannel",
    "InboundEvent",
    "KnowledgeBase",
    "LoginAttempt",
    "McpServer",
    "Membership",
    "Message",
    "Model",
    "Organization",
    "OtpCode",
    "Payment",
    "Plan",
    "PriceHistory",
    "Prompt",
    "PromptExample",
    "PromptVersion",
    "Provider",
    "ProviderAdapter",
    "Run",
    "Tool",
    "ToolInvocation",
    "TraceSpan",
    "Translation",
    "UsageLedger",
    "User",
    "UserMfa",
    "UserSession",
    "Wallet",
    "WalletTransaction",
]

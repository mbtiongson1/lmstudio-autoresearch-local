from pydantic import BaseModel
from typing import Optional, List, Union, Dict, Any


class ResearchRequest(BaseModel):
    topic: str
    max_turns: int = 8
    integrations: Optional[List[Dict[str, Any]]] = None


class ResearchStatus(BaseModel):
    task_id: str
    status: str  # "started", "running", "completed", "error"
    current_turn: int
    history: List[dict]


class ActionEvent(BaseModel):
    type: str  # "action", "complete", "error"
    turn: int
    action: str  # "search", "think", "answer"
    content: str


class ModelInstanceConfig(BaseModel):
    context_length: int
    eval_batch_size: Optional[int] = None
    flash_attention: Optional[bool] = None
    num_experts: Optional[int] = None
    offload_kv_cache_to_gpu: Optional[bool] = None


class ModelInstance(BaseModel):
    id: str
    config: ModelInstanceConfig


class ModelQuantization(BaseModel):
    name: Optional[str] = None
    bits_per_weight: Optional[int] = None


class ModelCapabilities(BaseModel):
    vision: bool
    trained_for_tool_use: bool


class ModelInfo(BaseModel):
    type: str  # "llm" | "embedding"
    publisher: str
    key: str
    display_name: str
    architecture: Optional[str] = None
    quantization: Optional[ModelQuantization] = None
    size_bytes: int
    params_string: Optional[str] = None
    loaded_instances: List[ModelInstance]
    max_context_length: int
    format: Optional[str] = None  # "gguf" | "mlx"
    capabilities: Optional[ModelCapabilities] = None
    description: Optional[str] = None


class ModelsListResponse(BaseModel):
    models: List[ModelInfo]


class ModelLoadRequest(BaseModel):
    model: str
    context_length: Optional[int] = None
    eval_batch_size: Optional[int] = None
    flash_attention: Optional[bool] = None
    num_experts: Optional[int] = None
    offload_kv_cache_to_gpu: Optional[bool] = None
    echo_load_config: bool = False


class ModelUnloadRequest(BaseModel):
    instance_id: str

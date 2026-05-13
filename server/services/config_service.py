import copy
import os
import traceback
import aiofiles
import toml
from typing import Any, Dict, TypedDict, Literal, Optional

# 定义配置文件的类型结构


class ModelConfig(TypedDict, total=False):
    type: Literal["text", "image", "video"]
    is_custom: Optional[bool]
    is_disabled: Optional[bool]


class ProviderConfig(TypedDict, total=False):
    url: str
    api_key: str
    max_tokens: int
    models: Dict[str, ModelConfig]
    is_custom: Optional[bool]
    model_name: Optional[str]
    download_retry_attempts: Optional[int]
    download_retry_delay_seconds: Optional[int]
    max_wait_seconds: Optional[int]


AppConfig = Dict[str, ProviderConfig]


DEFAULT_PROVIDERS_CONFIG: AppConfig = {
    'apipodcode': {
        'models': {
            'gpt-5.4': {'type': 'text'},
        },
        'url': 'https://api.apipod.ai/v1',
        'api_key': '',
        'max_tokens': 8192,
    },
    'apipodvideo': {
        'models': {
            'veo3-1-quality': {'type': 'video'},
        },
        'url': 'https://api.apipod.ai/v1/videos/generations',
        'api_key': '',
        'model_name': 'veo3-1-quality',
        'max_tokens': 8192,
        'download_retry_attempts': 3,
        'download_retry_delay_seconds': 2,
    },
    'apipodgptimage': {
        'models': {},
        'url': 'https://api.apipod.ai/v1/images/generations',
        'api_key': '',
        'model_name': 'gpt-image-2',
        'max_tokens': 8192,
    },
}

SERVER_DIR = os.path.dirname(os.path.dirname(__file__))
USER_DATA_DIR = os.getenv(
    "USER_DATA_DIR",
    os.path.join(SERVER_DIR, "user_data"),
)
FILES_DIR = os.path.join(USER_DATA_DIR, "files")


IMAGE_FORMATS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",  # 基础格式
    ".bmp",
    ".tiff",
    ".tif",  # 其他常见格式
    ".webp",
)
VIDEO_FORMATS = (
    ".mp4",
    ".avi",
    ".mkv",
    ".mov",
    ".wmv",
    ".flv",
)


class ConfigService:
    def __init__(self):
        self.app_config: AppConfig = copy.deepcopy(DEFAULT_PROVIDERS_CONFIG)
        self.config_file = os.getenv(
            "CONFIG_PATH", os.path.join(USER_DATA_DIR, "config.toml")
        )
        self.initialized = False

    async def initialize(self) -> None:
        try:
            # Ensure the user_data directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

            # Check if config file exists
            if not self.exists_config():
                print(
                    f"Config file not found at {self.config_file}, creating default configuration")
                # Create default config file
                with open(self.config_file, "w") as f:
                    toml.dump(self.app_config, f)
                print(f"Default config file created at {self.config_file}")
                self.initialized = True
                return

            async with aiofiles.open(self.config_file, "r") as f:
                content = await f.read()
                config: AppConfig = toml.loads(content)
            self.app_config = self._sanitize_config(config)
            with open(self.config_file, "w") as f:
                toml.dump(self.app_config, f)

        except Exception as e:
            print(f"Error loading config: {e}")
            traceback.print_exc()
        finally:
            self.initialized = True

    def get_config(self) -> AppConfig:
        return self.app_config

    async def update_config(self, data: AppConfig) -> Dict[str, str]:
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            sanitized = self._sanitize_config(data)
            with open(self.config_file, "w") as f:
                toml.dump(sanitized, f)
            self.app_config = sanitized

            return {
                "status": "success",
                "message": "Application settings updated successfully",
            }
        except Exception as e:
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def exists_config(self) -> bool:
        return os.path.exists(self.config_file)

    def get_public_config(self) -> AppConfig:
        public_config = copy.deepcopy(self.app_config)
        for provider_config in public_config.values():
            if "api_key" in provider_config:
                provider_config["api_key"] = ""
        return public_config

    def _sanitize_config(self, data: Dict[str, Any] | AppConfig) -> AppConfig:
        sanitized = copy.deepcopy(DEFAULT_PROVIDERS_CONFIG)
        for provider_name, provider_defaults in DEFAULT_PROVIDERS_CONFIG.items():
            provider_data = data.get(provider_name, {}) if isinstance(data, dict) else {}
            if not isinstance(provider_data, dict):
                provider_data = {}

            merged = copy.deepcopy(provider_defaults)
            for field in (
                "url",
                "api_key",
                "max_tokens",
                "download_retry_attempts",
                "download_retry_delay_seconds",
                "max_wait_seconds",
            ):
                if field in provider_data and provider_data[field] not in (None, ""):
                    merged[field] = provider_data[field]

            if provider_name == "apipodvideo":
                merged["model_name"] = "veo3-1-quality"
            elif provider_name == "apipodgptimage":
                merged["model_name"] = "gpt-image-2"
            else:
                merged["models"] = copy.deepcopy(provider_defaults.get("models", {}))

            merged["models"] = copy.deepcopy(provider_defaults.get("models", {}))
            sanitized[provider_name] = merged

        return sanitized


config_service = ConfigService()

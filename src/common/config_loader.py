import os
from dotenv import load_dotenv

class ConfigLoader:
    """配置加载器 - 从 .env 文件读取配置"""
    
    _loaded = False
    
    @classmethod
    def _load(cls):
        """加载 .env 文件"""
        if not cls._loaded:
            env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
            if os.path.exists(env_path):
                load_dotenv(env_path)
                print("[ConfigLoader] 配置已加载")
            else:
                print("[ConfigLoader] .env 文件未找到")
            cls._loaded = True
    
    @classmethod
    def get(cls, key: str, default: str = '') -> str:
        """获取配置值"""
        cls._load()
        return os.getenv(key, default)
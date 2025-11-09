"""
Configuration Loader
"""

import yaml
import os
import re
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def load_config(config_path: str = 'config.yaml') -> Dict[str, Any]:
    """
    Load configuration from YAML file with environment variable substitution
    
    Args:
        config_path: Path to config file
        
    Returns:
        Configuration dictionary
    """
    path = Path(config_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(path, 'r') as f:
        config_text = f.read()
    
    # Substitute environment variables
    config_text = substitute_env_vars(config_text)
    
    # Parse YAML
    config = yaml.safe_load(config_text)
    
    # Validate required sections
    validate_config(config)
    
    logger.debug(f"Loaded configuration from {config_path}")
    
    return config


def substitute_env_vars(text: str) -> str:
    """
    Replace ${ENV_VAR} patterns with environment variable values
    
    Args:
        text: Text containing ${VAR} patterns
        
    Returns:
        Text with substituted values
    """
    pattern = re.compile(r'\$\{([^}]+)\}')
    
    def replacer(match):
        var_name = match.group(1)
        value = os.getenv(var_name)
        
        if value is None:
            logger.warning(f"Environment variable not found: {var_name}")
            return match.group(0)  # Keep original if not found
        
        return value
    
    return pattern.sub(replacer, text)


def validate_config(config: Dict[str, Any]):
    """
    Validate configuration has required sections
    
    Args:
        config: Configuration dictionary
        
    Raises:
        ValueError: If configuration is invalid
    """
    required_sections = ['ai', 'api', 'testing', 'execution', 'reporting']
    
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required configuration section: {section}")
    
    # Validate AI config
    ai_config = config['ai']
    if 'provider' not in ai_config:
        raise ValueError("AI provider not specified in configuration")
    
    # Check API key is available (CRITICAL FIX)
    api_key_env = ai_config.get('api_key_env', 'ANTHROPIC_API_KEY')
    if not os.getenv(api_key_env):
        raise ValueError(
            f"Required environment variable not set: {api_key_env}\n"
            f"Please set it in your .env file or environment.\n"
            f"Example: export {api_key_env}=your_api_key_here"
        )


def get_config_value(config: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    """
    Get nested configuration value using dot notation
    
    Args:
        config: Configuration dictionary
        key_path: Dot-separated key path (e.g., 'ai.model')
        default: Default value if key not found
        
    Returns:
        Configuration value or default
    """
    keys = key_path.split('.')
    value = config
    
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    
    return value


def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge two configuration dictionaries
    
    Args:
        base: Base configuration
        override: Override configuration
        
    Returns:
        Merged configuration
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    
    return result


def create_default_config(output_path: str = 'config.yaml') -> Path:
    """
    Create a default configuration file
    
    Args:
        output_path: Where to write the config file
        
    Returns:
        Path to created config file
    """
    output = Path(output_path)
    
    if output.exists():
        logger.warning(f"Configuration file already exists: {output_path}")
        return output
    
    # Check if example exists
    example_path = Path('config.yaml.example')
    
    if example_path.exists():
        # Copy example to target
        import shutil
        shutil.copy(example_path, output)
        logger.info(f"Created {output_path} from config.yaml.example")
    else:
        logger.error("config.yaml.example not found. Please create configuration manually.")
        raise FileNotFoundError("config.yaml.example not found")
    
    return output


def validate_api_config(config: Dict[str, Any]) -> bool:
    """
    Validate API configuration is properly set up
    
    Args:
        config: Configuration dictionary
        
    Returns:
        True if valid, False otherwise
    """
    api_config = config.get('api', {})
    
    # Check base URL
    if not api_config.get('base_url'):
        logger.error("API base_url not configured")
        return False
    
    # Check auth configuration
    auth = api_config.get('auth', {})
    auth_type = auth.get('type', 'none')
    
    if auth_type == 'api_key':
        if not auth.get('api_key'):
            logger.warning("API key auth configured but api_key not provided")
    elif auth_type == 'bearer':
        if not auth.get('token'):
            logger.warning("Bearer auth configured but token not provided")
    elif auth_type == 'basic':
        if not auth.get('username') or not auth.get('password'):
            logger.warning("Basic auth configured but credentials not provided")
    
    return True


def save_config(config: Dict[str, Any], output_path: str = 'config.yaml') -> Path:
    """
    Save configuration to YAML file
    
    Args:
        config: Configuration dictionary
        output_path: Where to write the config file
        
    Returns:
        Path to saved config file
    """
    output = Path(output_path)
    
    with open(output, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    logger.info(f"Configuration saved to {output_path}")
    
    return output

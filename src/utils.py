"""
Utility functions
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)


def setup_logging(verbose: bool = False) -> logging.Logger:
    """
    Setup logging configuration
    
    Args:
        verbose: Enable debug logging
        
    Returns:
        Configured logger
    """
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    level = logging.DEBUG if verbose else logging.INFO
    
    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler with color
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(ColoredFormatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    ))
    
    # File handler
    file_handler = logging.FileHandler(log_dir / 'test_execution.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    return root_logger


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors"""
    
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
    }
    
    def format(self, record):
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{Style.RESET_ALL}"
        return super().format(record)


def print_banner():
    """Print application banner"""
    banner = f"""
{Fore.CYAN}{'='*70}
    AI-Powered API Testing Framework
    Version 1.0.0
{'='*70}{Style.RESET_ALL}
"""
    print(banner)


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format"""
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.1f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def safe_filename(name: str) -> str:
    """Convert string to safe filename"""
    # Remove/replace unsafe characters
    safe = ''.join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in name)
    # Replace spaces with underscores
    safe = safe.replace(' ', '_')
    # Remove duplicate underscores
    while '__' in safe:
        safe = safe.replace('__', '_')
    return safe.strip('_').lower()


def truncate_string(s: str, max_length: int = 100, suffix: str = '...') -> str:
    """Truncate string to maximum length"""
    if len(s) <= max_length:
        return s
    return s[:max_length - len(suffix)] + suffix


def calculate_percentage(part: int, total: int) -> float:
    """Calculate percentage safely"""
    if total == 0:
        return 0.0
    return (part / total) * 100


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists"""
    path.mkdir(parents=True, exist_ok=True)
    return path


def format_bytes(bytes_count: int) -> str:
    """Format bytes in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.1f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.1f} TB"


def parse_curl_command(curl_cmd: str) -> dict:
    """Parse curl command into request components (basic implementation)"""
    # This is a simplified parser - full implementation would be more complex
    import shlex
    
    parts = shlex.split(curl_cmd)
    
    result = {
        'method': 'GET',
        'url': '',
        'headers': {},
        'data': None
    }
    
    i = 0
    while i < len(parts):
        if parts[i] == 'curl':
            i += 1
            continue
        
        if parts[i] in ('-X', '--request'):
            result['method'] = parts[i + 1]
            i += 2
        elif parts[i] in ('-H', '--header'):
            header = parts[i + 1]
            if ':' in header:
                key, value = header.split(':', 1)
                result['headers'][key.strip()] = value.strip()
            i += 2
        elif parts[i] in ('-d', '--data'):
            result['data'] = parts[i + 1]
            i += 2
        elif not parts[i].startswith('-'):
            result['url'] = parts[i].strip("'\"")
            i += 1
        else:
            i += 1
    
    return result
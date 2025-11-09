"""
Test Executor - Runs pytest tests and collects results
"""

import subprocess
import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class TestExecutor:
    """Execute pytest tests and collect results"""
    
    def __init__(self, config: Dict):
        """Initialize test executor"""
        self.config = config
        self.results_dir = Path("test_results")
        self.results_dir.mkdir(exist_ok=True, parents=True)
        
        # Get timeout from config
        self.test_timeout = config.get('test_timeout', 300)
        logger.debug(f"Test execution timeout set to {self.test_timeout}s")
    
    def run_tests(self, test_files: List[str], api_config: Dict) -> Dict[str, Any]:
        """
        Run pytest tests and collect results
        
        Args:
            test_files: List of test file paths
            api_config: API configuration for tests
            
        Returns:
            Dictionary containing test results
        """
        logger.info("Executing test suite...")
        
        start_time = time.time()
        
        # Prepare pytest arguments
        pytest_args = self._build_pytest_args(test_files)
        
        # Run pytest
        result = self._run_pytest(pytest_args)
        
        duration = time.time() - start_time
        
        # Parse results
        test_results = self._parse_results(result, duration)
        
        logger.info(f"Test execution complete: {test_results['passed']}/{test_results['total_tests']} passed")
        
        return test_results
    
    def _build_pytest_args(self, test_files: List[str]) -> List[str]:
        """Build pytest command arguments"""
        
        # Base arguments
        args = [
            'pytest',
            '-v',  # Verbose
            '--tb=short',  # Short traceback
            '--color=yes',
        ]
        
        # JSON report for parsing
        json_report = self.results_dir / 'report.json'
        args.extend([
            '--json-report',
            f'--json-report-file={json_report}',
            '--json-report-indent=2'
        ])
        
        # HTML report
        html_report = self.results_dir / 'pytest_report.html'
        args.extend([
            '--html={}'.format(html_report),
            '--self-contained-html'
        ])
        
        # Add test directories/files - Remove duplicates
        test_paths = set()  # Use set to avoid duplicates
        
        for test_file in test_files:
            path = Path(test_file)
            if path.name != 'conftest.py':  # Skip conftest
                test_paths.add(str(path))
        
        # If all tests are in same directory, just use the directory
        if test_paths:
            # Get unique directories
            directories = set(Path(p).parent for p in test_paths)
            
            if len(directories) == 1:
                # All tests in same dir - run the whole directory
                args.append(str(list(directories)[0]))
            else:
                # Tests in multiple dirs - add each unique file
                args.extend(sorted(test_paths))
        
        return args
    
    def _run_pytest(self, args: List[str]) -> subprocess.CompletedProcess:
        """Run pytest command"""
        
        logger.debug(f"Running: {' '.join(args)}")
        
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=self.test_timeout  # Use timeout from config
            )
            
            # Log output
            if result.stdout:
                logger.debug(f"Pytest stdout:\n{result.stdout}")
            if result.stderr:
                logger.debug(f"Pytest stderr:\n{result.stderr}")
            
            return result
            
        except subprocess.TimeoutExpired:
            logger.error(f"Test execution timed out after {self.test_timeout}s")
            raise
        except Exception as e:
            logger.error(f"Failed to run pytest: {e}")
            raise
    
    def _parse_results(self, result: subprocess.CompletedProcess, duration: float) -> Dict[str, Any]:
        """Parse pytest results from JSON report"""
        
        json_report = self.results_dir / 'report.json'
        
        # Default results structure
        results = {
            'timestamp': datetime.now().isoformat(),
            'duration': duration,
            'total_tests': 0,
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'errors': 0,
            'pass_rate': 0.0,
            'tests': [],
            'failures': [],
            'summary': {},
            'raw_output': result.stdout
        }
        
        # Parse JSON report if available
        if json_report.exists():
            try:
                with open(json_report, 'r') as f:
                    json_data = json.load(f)
                
                summary = json_data.get('summary', {})
                results['total_tests'] = summary.get('total', 0)
                results['passed'] = summary.get('passed', 0)
                results['failed'] = summary.get('failed', 0)
                results['skipped'] = summary.get('skipped', 0)
                
                # Add debug logging
                logger.debug(f"Parsed from JSON: {results['total_tests']} total, "
                            f"{results['passed']} passed, {results['failed']} failed")
                
                # Calculate pass rate
                if results['total_tests'] > 0:
                    results['pass_rate'] = (results['passed'] / results['total_tests']) * 100
                
                # Extract test details
                for test in json_data.get('tests', []):
                    # Get duration from call phase (most accurate)
                    duration = 0
                    if 'call' in test and 'duration' in test['call']:
                        duration = test['call']['duration']
                    elif 'duration' in test:
                        duration = test['duration']
                    
                    test_info = {
                        'name': test.get('nodeid', ''),
                        'outcome': test.get('outcome', 'unknown'),
                        'duration': float(duration),
                        'file': test.get('location', [''])[0],
                        'line': test.get('location', [0, 0])[1] if len(test.get('location', [])) > 1 else 0
                    }
                    
                    results['tests'].append(test_info)
                    
                    # Collect failures
                    if test.get('outcome') == 'failed':
                        failure_info = test_info.copy()
                        failure_info['message'] = test.get('call', {}).get('longrepr', 'No error message')
                        results['failures'].append(failure_info)
                
                results['summary'] = summary
                
            except Exception as e:
                logger.warning(f"Failed to parse JSON report: {e}")
        
        else:
            # Fallback: parse from stdout
            logger.warning("JSON report not found, parsing stdout")
            results = self._parse_stdout(result.stdout, duration)
        
        return results
    
    def _parse_stdout(self, stdout: str, duration: float) -> Dict[str, Any]:
        """Fallback: parse results from pytest stdout"""
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'duration': duration,
            'total_tests': 0,
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'errors': 0,
            'pass_rate': 0.0,
            'tests': [],
            'failures': [],
            'summary': {},
            'raw_output': stdout
        }
        
        # Look for summary line like "5 passed, 2 failed in 10.23s"
        for line in stdout.split('\n'):
            if 'passed' in line or 'failed' in line:
                if 'passed' in line:
                    try:
                        results['passed'] = int(line.split('passed')[0].strip().split()[-1])
                    except:
                        pass
                if 'failed' in line:
                    try:
                        results['failed'] = int(line.split('failed')[0].strip().split()[-1])
                    except:
                        pass
        
        results['total_tests'] = results['passed'] + results['failed']
        
        if results['total_tests'] > 0:
            results['pass_rate'] = (results['passed'] / results['total_tests']) * 100
        
        return results


def format_test_results(results: Dict[str, Any]) -> str:
    """Format test results for display"""
    
    output = f"""
Test Execution Results
======================
Timestamp:    {results['timestamp']}
Duration:     {results['duration']:.2f}s
Total Tests:  {results['total_tests']}
Passed:       {results['passed']} ({results['pass_rate']:.1f}%)
Failed:       {results['failed']}
Skipped:      {results['skipped']}
"""
    
    if results['failures']:
        output += "\nFailures:\n"
        for failure in results['failures'][:5]:  # Show first 5
            output += f"  - {failure['name']}\n"
            output += f"    {failure.get('message', 'No message')[:100]}\n"
    
    return output

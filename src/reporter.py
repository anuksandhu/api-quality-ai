"""
Reporter - Generate HTML reports and send email notifications
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


class Reporter:
    """Generate test reports and notifications"""
    
    def __init__(self, config: Dict):
        """Initialize reporter"""
        self.config = config
        
        # Setup Jinja2 environment
        template_dir = Path('templates')
        if not template_dir.exists():
            template_dir.mkdir(parents=True)
            self._create_default_template()
        
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )
    
    def generate_report(
        self,
        spec_data: Dict,
        test_results: Dict,
        analysis: Dict,
        output_dir: str = 'reports'
    ) -> Path:
        """
        Generate comprehensive HTML report
        
        Args:
            spec_data: Parsed API specification
            test_results: Test execution results
            analysis: AI analysis results
            output_dir: Output directory
            
        Returns:
            Path to generated report
        """
        logger.info("Generating HTML report...")
        
        # Prepare report data
        report_data = self._prepare_report_data(spec_data, test_results, analysis)
        
        # Render template
        template = self.env.get_template('report_template.html')
        html_content = template.render(**report_data)
        
        # Write report
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True, parents=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = output_path / f'test_report_{timestamp}.html'
        
        report_file.write_text(html_content, encoding='utf-8')
        
        logger.info(f"Report generated: {report_file}")
        
        return report_file
    
    def _prepare_report_data(
        self,
        spec_data: Dict,
        test_results: Dict,
        analysis: Dict
    ) -> Dict[str, Any]:
        """Prepare data for report template"""
        
        # Executive summary
        executive_summary = {
            'api_name': spec_data['info']['title'],
            'api_version': spec_data['info']['version'],
            'test_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_tests': test_results['total_tests'],
            'passed': test_results['passed'],
            'failed': test_results['failed'],
            'skipped': test_results.get('skipped', 0),
            'pass_rate': test_results['pass_rate'],
            'duration': test_results['duration'],
            'status': 'PASSED' if test_results['failed'] == 0 else 'FAILED'
        }
        
        # Coverage metrics
        coverage = {
            'total_endpoints': len(spec_data['endpoints']),
            'tested_endpoints': analysis.get('total_scenarios', 0),
            'coverage_percentage': analysis.get('coverage_percentage', 0),
            'untested_endpoints': []
        }
        
        # Test breakdown by type
        test_breakdown = self._calculate_test_breakdown(test_results)
        
        # Failure analysis
        failure_analysis = self._analyze_failures(test_results)
        
        # Performance metrics
        performance = self._calculate_performance_metrics(test_results)
        
        return {
            'executive_summary': executive_summary,
            'coverage': coverage,
            'test_breakdown': test_breakdown,
            'test_results': test_results,
            'failure_analysis': failure_analysis,
            'performance': performance,
            'spec_data': spec_data,
            'analysis': analysis,
            'generated_at': datetime.now().isoformat()
        }
    
    def _calculate_test_breakdown(self, test_results: Dict) -> Dict[str, int]:
        """Calculate test breakdown by category"""
        
        # Initialize breakdown
        breakdown = {
            'positive': 0,
            'negative': 0,
            'edge_case': 0,
            'security': 0,
            'other': 0
        }
        
        # Try to use analysis data (most accurate)
        if hasattr(self, '_analysis_data') and self._analysis_data:
            logger.debug("Using AI analysis data for test breakdown")
            for scenario in self._analysis_data.get('test_scenarios', []):
                test_type = scenario.get('test_type', 'other')
                if test_type in breakdown:
                    breakdown[test_type] += 1
                else:
                    breakdown['other'] += 1
            
            logger.debug(f"Test breakdown from analysis: {breakdown}")
            return breakdown
        
        # Fallback: Parse test names with improved keyword matching
        logger.debug("Falling back to test name parsing for breakdown")
        
        for test in test_results.get('tests', []):
            name = test.get('name', '').lower()
            
            # Expanded keyword matching
            if any(word in name for word in [
                'valid', 'successful', 'retrieve_existing', 'create_valid',
                'successfully', 'positive', 'retrieve_all'
            ]):
                breakdown['positive'] += 1
            elif any(word in name for word in [
                'invalid', 'missing', 'malformed', 'non_existent',
                'negative', 'incorrect', 'wrong'
            ]):
                breakdown['negative'] += 1
            elif any(word in name for word in [
                'edge', 'boundary', 'maximum', 'minimum', 'zero',
                'null', 'negative_id', 'special_characters', 'empty',
                'concurrent', 'mass_', 'very_large'
            ]):
                breakdown['edge_case'] += 1
            elif any(word in name for word in [
                'security', 'auth', 'injection', 'xss', 'enumeration',
                'disclosure', 'rate_limit', 'rate_limiting', 'sql_injection'
            ]):
                breakdown['security'] += 1
            else:
                breakdown['other'] += 1
        
        logger.debug(f"Test breakdown from names: {breakdown}")
        return breakdown
    
    def _analyze_failures(self, test_results: Dict) -> Dict[str, Any]:
        """Analyze failure patterns"""
        failures = test_results.get('failures', [])
        
        if not failures:
            return {
                'total': 0,
                'by_category': {},
                'top_failures': []
            }
        
        # Group by error type
        by_category = {}
        for failure in failures:
            # Simple categorization based on message
            message = failure.get('message', '').lower()
            
            if 'timeout' in message:
                category = 'Timeout'
            elif 'authentication' in message or 'auth' in message:
                category = 'Authentication'
            elif '404' in message or 'not found' in message:
                category = 'Not Found'
            elif '500' in message or 'server error' in message:
                category = 'Server Error'
            elif 'assertion' in message:
                category = 'Assertion Failed'
            else:
                category = 'Other'
            
            by_category[category] = by_category.get(category, 0) + 1
        
        return {
            'total': len(failures),
            'by_category': by_category,
            'top_failures': failures[:5]  # Top 5 failures
        }
    
    def _calculate_performance_metrics(self, test_results: Dict) -> Dict[str, Any]:
        """Calculate performance metrics"""
        tests = test_results.get('tests', [])
        
        if not tests:
            return {
                'avg_duration': 0,
                'min_duration': 0,
                'max_duration': 0,
                'slow_tests': []
            }
        
        durations = [t.get('duration', 0) for t in tests]
        
        avg_duration = sum(durations) / len(durations) if durations else 0
        min_duration = min(durations) if durations else 0
        max_duration = max(durations) if durations else 0
        
        # Find slow tests (>2 seconds)
        slow_tests = [
            t for t in tests
            if t.get('duration', 0) > 2.0
        ]
        slow_tests.sort(key=lambda x: x.get('duration', 0), reverse=True)
        
        return {
            'avg_duration': avg_duration,
            'min_duration': min_duration,
            'max_duration': max_duration,
            'slow_tests': slow_tests[:5]  # Top 5 slowest
        }
    
    def send_email_report(self, report_path: Path, test_results: Dict):
        """
        Send email notification with report
        
        Args:
            report_path: Path to HTML report
            test_results: Test results for summary
        """
        email_config = self.config.get('email', {})
        
        if not email_config.get('enabled'):
            logger.debug("Email notifications disabled")
            return
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            
            subject_prefix = email_config.get('subject_prefix', '[API Tests]')
            status = 'PASSED' if test_results['failed'] == 0 else 'FAILED'
            msg['Subject'] = f"{subject_prefix} Test Report - {status}"
            msg['From'] = email_config['from_address']
            msg['To'] = ', '.join(email_config['to_addresses'])
            
            # Email body (plain text summary)
            text_body = self._create_email_text(test_results)
            msg.attach(MIMEText(text_body, 'plain'))
            
            # Read and attach HTML report
            html_body = report_path.read_text(encoding='utf-8')
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send email
            smtp_host = email_config['smtp_host']
            smtp_port = email_config['smtp_port']
            
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if email_config.get('use_tls', True):
                    server.starttls()
                
                username = email_config.get('username')
                password = email_config.get('password')
                
                if username and password:
                    server.login(username, password)
                
                server.send_message(msg)
            
            logger.info("Email report sent successfully")
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
    
    def _create_email_text(self, test_results: Dict) -> str:
        """Create plain text email body"""
        status = 'PASSED' if test_results['failed'] == 0 else 'FAILED'
        
        return f"""
API Test Report - {status}

Summary:
--------
Total Tests:  {test_results['total_tests']}
Passed:       {test_results['passed']} ({test_results['pass_rate']:.1f}%)
Failed:       {test_results['failed']}
Skipped:      {test_results.get('skipped', 0)}
Duration:     {test_results['duration']:.2f}s

{self._format_failures_for_email(test_results)}

See attached HTML report for full details.
"""
    
    def _format_failures_for_email(self, test_results: Dict) -> str:
        """Format failures for email"""
        failures = test_results.get('failures', [])
        
        if not failures:
            return "All tests passed! ✓"
        
        output = "Failed Tests:\n"
        for failure in failures[:5]:
            output += f"  - {failure['name']}\n"
        
        if len(failures) > 5:
            output += f"\n  ... and {len(failures) - 5} more failures\n"
        
        return output
    
    def _create_default_template(self):
        """Create default HTML template if it doesn't exist"""
        template_path = Path('templates/report_template.html')
        
        if template_path.exists():
            logger.debug(f"Template already exists: {template_path}")
            return
        
        # Ensure templates directory exists
        template_path.parent.mkdir(parents=True, exist_ok=True)
        
        # The actual template is provided separately in templates/report_template.html
        # This is just a fallback minimal template
        minimal_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>API Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #333; }
        .summary { background: #f0f0f0; padding: 20px; border-radius: 5px; }
        .metric { display: inline-block; margin: 10px 20px; }
        .passed { color: green; }
        .failed { color: red; }
    </style>
</head>
<body>
    <h1>API Test Report</h1>
    <div class="summary">
        <h2>{{ executive_summary.api_name }}</h2>
        <div class="metric">
            <strong>Total Tests:</strong> {{ executive_summary.total_tests }}
        </div>
        <div class="metric passed">
            <strong>Passed:</strong> {{ executive_summary.passed }}
        </div>
        <div class="metric failed">
            <strong>Failed:</strong> {{ executive_summary.failed }}
        </div>
        <div class="metric">
            <strong>Pass Rate:</strong> {{ "%.1f"|format(executive_summary.pass_rate) }}%
        </div>
    </div>
    <p><em>Note: Using minimal template. For better reports, use the full template from templates/report_template.html</em></p>
</body>
</html>"""
        
        template_path.write_text(minimal_template)
        logger.info(f"Created minimal template at {template_path}")
        logger.info("For professional reports, replace with the full template from templates/report_template.html")
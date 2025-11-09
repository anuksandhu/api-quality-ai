#!/usr/bin/env python3
"""
AI-Powered API Testing Framework
Main CLI entry point
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
from src.config_loader import load_config
from src.spec_parser import SpecParser
from src.ai_analyzer import AIAnalyzer
from src.test_generator import TestGenerator
from src.test_executor import TestExecutor
from src.reporter import Reporter
from src.utils import setup_logging, print_banner

def main():
    """Main execution flow"""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='AI-Powered API Testing Framework',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test using OpenAPI spec URL
  python main.py --spec https://api.example.com/openapi.json --config config.yaml
  
  # Test using local spec file
  python main.py --spec ./specs/petstore.yaml --config config.yaml
  
  # Generate tests only (no execution)
  python main.py --spec ./specs/api.json --generate-only
        """
    )
    
    parser.add_argument(
        '--spec',
        required=True,
        help='OpenAPI spec URL or local file path'
    )
    
    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Configuration file path (default: config.yaml)'
    )
    
    parser.add_argument(
        '--generate-only',
        action='store_true',
        help='Only generate tests, do not execute'
    )
    
    parser.add_argument(
        '--output-dir',
        default='reports',
        help='Output directory for reports (default: reports/)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(verbose=args.verbose)
    
    # Print banner
    print_banner()
    
    try:
        # Step 1: Load configuration
        logger.info("Loading configuration...")
        config = load_config(args.config)
        logger.info(f"✓ Configuration loaded from {args.config}")
        
        # Step 2: Parse OpenAPI spec
        logger.info(f"Parsing OpenAPI specification: {args.spec}")
        spec_parser = SpecParser(args.spec)
        spec_data = spec_parser.parse()
        logger.info(f"✓ Parsed {len(spec_data['endpoints'])} endpoints from spec")
        
        # Step 3: AI Analysis
        logger.info("Analyzing API with AI...")
        ai_analyzer = AIAnalyzer(config['ai'])
        analysis = ai_analyzer.analyze_spec(spec_data)
        logger.info(f"✓ AI generated test strategy for {len(analysis['test_scenarios'])} scenarios")
        
        # Step 4: Generate test code
        logger.info("Generating pytest test cases...")
        test_generator = TestGenerator(config['testing'])
        test_files = test_generator.generate_tests(spec_data, analysis)
        logger.info(f"✓ Generated {len(test_files)} test files in generated_tests/")
        
        if args.generate_only:
            logger.info("Test generation complete (--generate-only flag set)")
            logger.info(f"Generated tests are in: {Path('generated_tests').absolute()}")
            return 0
        
        # Step 5: Execute tests
        logger.info("Executing test suite...")
        executor = TestExecutor(config['execution'])
        test_results = executor.run_tests(test_files, config['api'])
        logger.info(f"✓ Executed {test_results['total_tests']} tests: "
                   f"{test_results['passed']} passed, "
                   f"{test_results['failed']} failed")
        
        # Step 6: Generate report
        logger.info("Generating test report...")
        reporter = Reporter(config['reporting'])

        # Pass analysis data for accurate test categorization
        reporter._analysis_data = analysis  # ← ADD THIS LINE

        report_path = reporter.generate_report(
            spec_data=spec_data,
            test_results=test_results,
            analysis=analysis,
            output_dir=args.output_dir
        )
        logger.info(f"✓ Report generated: {report_path}")
        
        # Step 7: Send email if configured
        if config['reporting'].get('email', {}).get('enabled'):
            logger.info("Sending email report...")
            reporter.send_email_report(report_path, test_results)
            logger.info("✓ Email sent successfully")
        
        # Summary
        print("\n" + "="*70)
        print("🎉 TEST EXECUTION COMPLETE")
        print("="*70)
        print(f"Total Tests:     {test_results['total_tests']}")  # ← Make sure this is from test_results
        print(f"Passed:          {test_results['passed']} ({test_results['pass_rate']:.1f}%)")
        print(f"Failed:          {test_results['failed']}")
        print(f"Skipped:         {test_results.get('skipped', 0)}")
        print(f"Duration:        {test_results['duration']:.2f}s")
        print(f"\nReport:          {report_path}")
        print("="*70 + "\n")
        
        # Exit code based on test results
        return 0 if test_results['failed'] == 0 else 1
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Interrupted by user")
        return 130
        
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}", exc_info=args.verbose)
        return 1

if __name__ == '__main__':
    sys.exit(main())
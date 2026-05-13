"""
GoodQ Analytics CLI
Command-line interface for analytics system
"""
import sys
from pathlib import Path
import argparse

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from steps.common.config_loader import get_runtime_paths, load_configs

def main():
    parser = argparse.ArgumentParser(
        description='GoodQ Analytics System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate global dashboard
  python analytics_cli.py dashboard
  
  # Analyze specific video
  python analytics_cli.py analyze <video_path>
  
  # Interactive queries
  python analytics_cli.py query
  
  # Query with specific video
  python analytics_cli.py query --video <video_path> --question "What emotions?"
  
  # Run full test
  python analytics_cli.py test
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Dashboard command
    dashboard_parser = subparsers.add_parser('dashboard', help='Generate global dashboard')
    dashboard_parser.add_argument('-o', '--output', default=None,
                                  help='Output file path')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze specific video')
    analyze_parser.add_argument('video', help='Video path or hash')
    analyze_parser.add_argument('-o', '--output-dir', default=None,
                               help='Output directory')
    analyze_parser.add_argument('--json-only', action='store_true',
                               help='Export JSON only')
    analyze_parser.add_argument('--md-only', action='store_true',
                               help='Export Markdown only')
    
    # Query command
    query_parser = subparsers.add_parser('query', help='Query the analytics system')
    query_parser.add_argument('-q', '--question', help='Question to ask')
    query_parser.add_argument('-v', '--video', help='Specific video to query')
    query_parser.add_argument('-i', '--interactive', action='store_true',
                             help='Start interactive session')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Run analytics test suite')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show quick statistics')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    config = load_configs({})
    runtime_paths = get_runtime_paths(config, 'output_directory')
    output_root = Path(runtime_paths['output_directory']).resolve()
    
    # Execute command
    if args.command == 'dashboard':
        from analytics_dashboard import AnalyticsDashboard
        dashboard = AnalyticsDashboard(config)
        output_path = Path(args.output).resolve() if args.output else (output_root / 'analytics_dashboard.md')
        dashboard.generate_dashboard(output_path)
        print(f"\n[SYMBOL] Dashboard generated: {output_path}")
        
    elif args.command == 'analyze':
        from analytics_engine import AnalyticsEngine, export_markdown_report, export_report_to_file
        
        engine = AnalyticsEngine(config)
        print(f"\nAnalyzing: {args.video}")
        report = engine.generate_comprehensive_report(args.video)
        
        output_dir = Path(args.output_dir).resolve() if args.output_dir else output_root
        output_dir.mkdir(exist_ok=True, parents=True)
        
        video_name = Path(args.video).stem
        
        if not args.md_only:
            json_path = output_dir / f"{video_name}_analytics.json"
            export_report_to_file(report, json_path)
            print(f"[SYMBOL] JSON report: {json_path}")
        
        if not args.json_only:
            md_path = output_dir / f"{video_name}_analytics.md"
            export_markdown_report(report, md_path)
            print(f"[SYMBOL] Markdown report: {md_path}")
        
        # Show summary
        print(f"\nSummary:")
        print(f"  Scenes: {report['summary'].get('total_scenes', 0)}")
        print(f"  Duration: {report['summary'].get('total_duration', 0):.1f}s")
        print(f"  Entities: {report['summary'].get('entities_detected', 0)}")
        print(f"  Insights: {len(report.get('key_insights', []))}")
        
    elif args.command == 'query':
        from analytics_query import AnalyticsQuery, interactive_query_session
        
        if args.interactive or not args.question:
            interactive_query_session(config)
        else:
            query_engine = AnalyticsQuery(config)
            result = query_engine.query(args.question, args.video)
            
            print(f"\nQuestion: {args.question}")
            if args.video:
                print(f"Video: {args.video}")
            print(f"\n{'='*60}")
            
            if result.get('answer'):
                print(f"\nAnswer: {result['answer']}")
                print(f"Confidence: {result.get('confidence', 0.0):.2f}")
            
            if result.get('data'):
                print(f"\nData available: {list(result['data'].keys())}")
                
    elif args.command == 'test':
        import subprocess
        subprocess.run([sys.executable, 'test_phase7_analytics.py'])
        
    elif args.command == 'stats':
        import sqlite3
        
        print("\n" + "="*60)
        print(" Quick Statistics")
        print("="*60)
        
        # Memory DB stats
        with sqlite3.connect(config['paths']['db_path']) as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(DISTINCT video_hash) FROM scenes")
            videos = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM scenes")
            scenes = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(end - start) FROM scenes")
            duration = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT modality, COUNT(*) FROM embeddings GROUP BY modality")
            embeddings = dict(cursor.fetchall())
        
        # KG stats
        with sqlite3.connect(config['paths']['knowledge_graph_db']) as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM nodes")
            nodes = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM edges")
            edges = cursor.fetchone()[0]
            
            cursor.execute("SELECT node_type, COUNT(*) FROM nodes GROUP BY node_type")
            node_types = dict(cursor.fetchall())
        
        print(f"\nProcessing:")
        print(f"  Videos: {videos}")
        print(f"  Scenes: {scenes}")
        print(f"  Total Duration: {duration/60:.1f} minutes")
        
        print(f"\nEmbeddings:")
        for modality, count in embeddings.items():
            print(f"  {modality.title()}: {count}")
        
        print(f"\nKnowledge Graph:")
        print(f"  Total Nodes: {nodes}")
        print(f"  Total Edges: {edges}")
        
        print(f"\nNode Types:")
        for node_type, count in sorted(node_types.items(), key=lambda x: x[1], reverse=True):
            print(f"  {node_type.title()}: {count}")
        
        print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()

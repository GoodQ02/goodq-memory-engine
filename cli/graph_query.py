"""
Knowledge Graph Query CLI
Command-line interface for querying the knowledge graph
"""
import sys
import click
import json
from pathlib import Path
from tabulate import tabulate

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.graph_query import GraphQuery


@click.group()
@click.option('--graph-db', default='L:/goodq4all/data/knowledge_graph.db', help='Path to knowledge graph database')
@click.pass_context
def cli(ctx, graph_db):
    """Query the GoodQ Knowledge Graph"""
    ctx.ensure_object(dict)
    ctx.obj['graph_db'] = graph_db


@cli.command()
@click.pass_context
def stats(ctx):
    """Show knowledge graph statistics"""
    with GraphQuery(ctx.obj['graph_db']) as gq:
        stats = gq.kg.get_statistics()
        
        click.echo("\n=== Knowledge Graph Statistics ===\n")
        
        click.echo("Nodes by Type:")
        for node_type, count in stats['nodes_by_type'].items():
            click.echo(f"  {node_type}: {count}")
        
        click.echo(f"\nTotal Nodes: {stats['total_nodes']}")
        click.echo(f"Total Edges: {stats['total_edges']}")
        click.echo(f"Total Media: {stats['total_media']}")
        click.echo(f"Total Events: {stats['total_events']}")
        
        if stats['edges_by_type']:
            click.echo("\nEdges by Type:")
            for edge_type, count in stats['edges_by_type'].items():
                click.echo(f"  {edge_type}: {count}")


@cli.command()
@click.argument('person_name')
@click.pass_context
def find_person(ctx, person_name):
    """Find all appearances of a person"""
    with GraphQuery(ctx.obj['graph_db']) as gq:
        appearances = gq.find_person_appearances(person_name)
        
        if not appearances:
            click.echo(f"No appearances found for '{person_name}'")
            return
        
        click.echo(f"\n=== Appearances of '{person_name}' ===\n")
        
        table_data = []
        for app in appearances:
            table_data.append([
                app['scene_id'],
                f"{app['timestamp_start']:.1f}s",
                f"{app['timestamp_end'] - app['timestamp_start']:.1f}s",
                f"{app['confidence']:.2f}"
            ])
        
        click.echo(tabulate(table_data, headers=['Scene', 'Start', 'Duration', 'Confidence']))


@cli.command()
@click.argument('scene_id')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
@click.pass_context
def scene_context(ctx, scene_id, as_json):
    """Get full context for a scene"""
    with GraphQuery(ctx.obj['graph_db']) as gq:
        context = gq.get_scene_context(scene_id)
        
        if not context:
            click.echo(f"Scene '{scene_id}' not found")
            return
        
        if as_json:
            click.echo(json.dumps(context, indent=2))
            return
        
        click.echo(f"\n=== Scene Context: {scene_id} ===\n")
        click.echo(f"Time: {context['timestamp_start']:.1f}s - {context['timestamp_end']:.1f}s")
        click.echo(f"Duration: {context['duration']:.1f}s")
        click.echo(f"Media: {context['media_path']}")
        
        click.echo("\nEntities:")
        for entity_type, entities in context['entities'].items():
            if entities:
                click.echo(f"\n  {entity_type.capitalize()}:")
                for ent in entities:
                    click.echo(f"    - {ent['name']} (confidence: {ent['confidence']:.2f})")
        
        if context.get('relationships'):
            click.echo("\nRelationships:")
            for rel in context['relationships']:
                click.echo(f"  {rel['source']} --[{rel['type']}]--> {rel['target']} (weight: {rel['weight']:.1f})")


@cli.command()
@click.argument('scene_id')
@click.option('--max-results', default=5, help='Maximum number of results')
@click.pass_context
def related_scenes(ctx, scene_id, max_results):
    """Find scenes related to a given scene"""
    with GraphQuery(ctx.obj['graph_db']) as gq:
        related = gq.find_related_scenes(scene_id, max_results=max_results)
        
        if not related:
            click.echo(f"No related scenes found for '{scene_id}'")
            return
        
        click.echo(f"\n=== Scenes Related to '{scene_id}' ===\n")
        
        table_data = []
        for scene in related:
            table_data.append([
                scene['scene_id'],
                f"{scene['timestamp_start']:.1f}s",
                f"{scene['timestamp_end'] - scene['timestamp_start']:.1f}s",
                scene['shared_nodes']
            ])
        
        click.echo(tabulate(table_data, headers=['Scene', 'Start', 'Duration', 'Shared Entities']))


@cli.command()
@click.argument('concept')
@click.pass_context
def track_concept(ctx, concept):
    """Track how a concept evolves over time"""
    with GraphQuery(ctx.obj['graph_db']) as gq:
        timeline = gq.find_concept_evolution(concept)
        
        if not timeline:
            click.echo(f"Concept '{concept}' not found")
            return
        
        click.echo(f"\n=== Evolution of '{concept}' ===\n")
        
        table_data = []
        for entry in timeline:
            table_data.append([
                entry['scene_id'],
                f"{entry['timestamp']:.1f}s",
                f"{entry['duration']:.1f}s",
                entry['node_type'],
                f"{entry['confidence']:.2f}"
            ])
        
        click.echo(tabulate(table_data, headers=['Scene', 'Time', 'Duration', 'Type', 'Confidence']))


@cli.command()
@click.option('--type', 'entity_type', help='Filter by entity type')
@click.option('--limit', default=20, help='Maximum number of entities to show')
@click.pass_context
def list_entities(ctx, entity_type, limit):
    """List entities in the graph"""
    with GraphQuery(ctx.obj['graph_db']) as gq:
        summary = gq.get_entity_summary(entity_type=entity_type)
        
        entities = summary['entities'][:limit]
        
        click.echo(f"\n=== Entities ({summary['count']} total) ===\n")
        
        table_data = []
        for ent in entities:
            first_seen = f"{ent['first_seen']:.1f}s" if ent['first_seen'] else "N/A"
            last_seen = f"{ent['last_seen']:.1f}s" if ent['last_seen'] else "N/A"
            
            table_data.append([
                ent['type'],
                ent['name'],
                ent['occurrences'],
                ent['media_count'],
                first_seen,
                last_seen
            ])
        
        click.echo(tabulate(table_data, headers=['Type', 'Name', 'Occurrences', 'Media', 'First', 'Last']))


@cli.command()
@click.option('--objects', multiple=True, help='Object names to search for')
@click.option('--emotions', multiple=True, help='Emotions to search for')
@click.option('--start-time', type=float, help='Start time in seconds')
@click.option('--end-time', type=float, help='End time in seconds')
@click.option('--min-confidence', type=float, default=0.0, help='Minimum confidence threshold')
@click.pass_context
def search(ctx, objects, emotions, start_time, end_time, min_confidence):
    """Search for scenes matching criteria"""
    criteria = {}
    
    if objects:
        criteria['objects'] = list(objects)
    if emotions:
        criteria['emotions'] = list(emotions)
    if start_time is not None and end_time is not None:
        criteria['time_range'] = (start_time, end_time)
    if min_confidence > 0:
        criteria['min_confidence'] = min_confidence
    
    if not criteria:
        click.echo("Please specify at least one search criterion")
        return
    
    with GraphQuery(ctx.obj['graph_db']) as gq:
        results = gq.search_by_multiple_criteria(criteria)
        
        if not results:
            click.echo("No matching scenes found")
            return
        
        click.echo(f"\n=== Search Results ({len(results)} scenes) ===\n")
        
        table_data = []
        for scene in results:
            table_data.append([
                scene['scene_id'],
                f"{scene['timestamp_start']:.1f}s",
                f"{scene['timestamp_end'] - scene['timestamp_start']:.1f}s",
                Path(scene['media_path']).name
            ])
        
        click.echo(tabulate(table_data, headers=['Scene', 'Start', 'Duration', 'Media']))


@cli.command()
@click.argument('start_time', type=float)
@click.argument('end_time', type=float)
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
@click.pass_context
def story(ctx, start_time, end_time, as_json):
    """Get a temporal narrative between timestamps"""
    with GraphQuery(ctx.obj['graph_db']) as gq:
        narrative = gq.find_temporal_story(start_time, end_time)
        
        if as_json:
            click.echo(json.dumps(narrative, indent=2))
            return
        
        click.echo(f"\n=== Story from {start_time:.1f}s to {end_time:.1f}s ===\n")
        
        if narrative['entities']:
            click.echo("Entities: " + ", ".join(narrative['entities']))
        
        if narrative['locations']:
            click.echo("Locations: " + ", ".join(narrative['locations']))
        
        if narrative['emotions']:
            click.echo("Emotions: " + ", ".join(narrative['emotions']))
        
        if narrative['events']:
            click.echo(f"\nEvents ({len(narrative['events'])}):")
            for event in narrative['events']:
                click.echo(f"  [{event['timestamp']:.1f}s] {event['event_type']}")
                for node in event.get('nodes', []):
                    click.echo(f"    - {node['name']} ({node['node_type']})")


@cli.command()
@click.argument('node_ids', nargs=-1, type=int)
@click.argument('output_path')
@click.pass_context
def export(ctx, node_ids, output_path):
    """Export subgraph as JSON"""
    if not node_ids:
        click.echo("Please specify at least one node ID")
        return
    
    with GraphQuery(ctx.obj['graph_db']) as gq:
        gq.kg.export_subgraph(list(node_ids), output_path)
        click.echo(f"Subgraph exported to {output_path}")


if __name__ == '__main__':
    cli()

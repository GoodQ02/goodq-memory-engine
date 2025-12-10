"""
Pipeline Flow Validator for GoodQ Multimodal Ingestion
Validates data contracts and flow through each pipeline step
"""
import json
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PipelineFlowValidator:
    """Validates data flow through the complete ingestion pipeline"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.validation_results = {
            'timestamp': datetime.now().isoformat(),
            'steps': {},
            'overall_status': 'UNKNOWN',
            'errors': [],
            'warnings': []
        }
    
    def validate_complete_flow(self, video_path: str) -> Dict[str, Any]:
        """Validate complete pipeline flow for a given video"""
        logger.info(f"Validating pipeline flow for: {video_path}")
        
        # Step 1: Validate video results JSON
        self.validate_video_results()
        
        # Step 2: Validate scene detection and extraction
        self.validate_scene_data()
        
        # Step 3: Validate multimodal analysis results
        self.validate_multimodal_analysis()
        
        # Step 4: Validate database storage
        self.validate_database_storage()
        
        # Step 5: Validate knowledge graph population
        self.validate_knowledge_graph()
        
        # Step 6: Validate embeddings and indices
        self.validate_embeddings()
        
        # Step 7: Validate LLM outputs
        self.validate_llm_outputs()
        
        # Determine overall status
        self._determine_overall_status()
        
        return self.validation_results
    
    def validate_video_results(self):
        """Validate video ingest results JSON"""
        step_name = "video_results"
        logger.info(f"Validating: {step_name}")
        
        results_path = Path("L:/goodq4all/logs/video_ingest_results.json")
        
        if not results_path.exists():
            self._add_error(step_name, "video_ingest_results.json not found")
            return
        
        try:
            with open(results_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                self._add_error(step_name, "Results should be a list")
                return
            
            if len(data) == 0:
                self._add_warning(step_name, "No videos processed")
                return
            
            # Validate structure of first video entry
            video = data[0]
            required_fields = ['video', 'scenes', 'frames']
            missing = [f for f in required_fields if f not in video]
            
            if missing:
                self._add_error(step_name, f"Missing required fields: {missing}")
            else:
                self._add_success(step_name, f"Found {len(data)} video(s) with proper structure")
                
                # Check data richness
                scene_count = len(video.get('scenes', []))
                frame_count = len(video.get('frames', []))
                
                self.validation_results['steps'][step_name]['metrics'] = {
                    'video_count': len(data),
                    'scene_count': scene_count,
                    'frame_count': frame_count
                }
                
        except json.JSONDecodeError as e:
            self._add_error(step_name, f"Invalid JSON: {e}")
        except Exception as e:
            self._add_error(step_name, f"Validation error: {e}")
    
    def validate_scene_data(self):
        """Validate scene detection and metadata"""
        step_name = "scene_data"
        logger.info(f"Validating: {step_name}")
        
        results_path = Path("L:/goodq4all/logs/video_ingest_results.json")
        
        try:
            with open(results_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not data:
                self._add_error(step_name, "No data to validate")
                return
            
            video = data[0]
            scenes = video.get('scenes', [])
            
            if not scenes:
                self._add_error(step_name, "No scenes detected")
                return
            
            # Validate scene structure
            required_scene_fields = ['start', 'end', 'index']
            issues = []
            
            for idx, scene in enumerate(scenes):
                missing = [f for f in required_scene_fields if f not in scene]
                if missing:
                    issues.append(f"Scene {idx} missing: {missing}")
            
            if issues:
                self._add_warning(step_name, f"Scene structure issues: {len(issues)}")
                self.validation_results['steps'][step_name]['issues'] = issues[:5]  # First 5
            else:
                self._add_success(step_name, f"All {len(scenes)} scenes properly structured")
                
                # Check for enriched data
                enriched_count = sum(1 for s in scenes if s.get('summary') or s.get('llm_summary'))
                if enriched_count > 0:
                    self.validation_results['steps'][step_name]['llm_enriched'] = enriched_count
                    
        except Exception as e:
            self._add_error(step_name, f"Validation error: {e}")
    
    def validate_multimodal_analysis(self):
        """Validate multimodal analysis outputs"""
        step_name = "multimodal_analysis"
        logger.info(f"Validating: {step_name}")
        
        results_path = Path("L:/goodq4all/logs/video_ingest_results.json")
        
        try:
            with open(results_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not data:
                self._add_error(step_name, "No data to validate")
                return
            
            video = data[0]
            frames = video.get('frames', [])
            
            # Check for various analysis outputs
            analysis_coverage = {
                'caption': 0,
                'ocr': 0,
                'objects': 0,
                'faces': 0,
                'embeddings': 0
            }
            
            for frame in frames:
                if frame.get('caption'):
                    analysis_coverage['caption'] += 1
                if frame.get('ocr_text'):
                    analysis_coverage['ocr'] += 1
                if frame.get('objects'):
                    analysis_coverage['objects'] += 1
                if frame.get('faces'):
                    analysis_coverage['faces'] += 1
                if frame.get('embedding'):
                    analysis_coverage['embeddings'] += 1
            
            total_frames = len(frames)
            coverage_pct = {k: (v / total_frames * 100) if total_frames > 0 else 0 
                           for k, v in analysis_coverage.items()}
            
            self.validation_results['steps'][step_name]['coverage'] = coverage_pct
            
            # Check audio analysis
            audio = video.get('audio', {})
            has_transcript = bool(audio.get('transcript'))
            has_speakers = bool(audio.get('speakers'))
            has_emotions = bool(audio.get('emotions'))
            
            audio_analysis = {
                'transcript': has_transcript,
                'speakers': has_speakers,
                'emotions': has_emotions
            }
            
            self.validation_results['steps'][step_name]['audio'] = audio_analysis
            
            # Overall assessment
            if coverage_pct['caption'] > 80 and has_transcript:
                self._add_success(step_name, "Comprehensive multimodal analysis")
            elif coverage_pct['caption'] > 50:
                self._add_warning(step_name, "Partial multimodal analysis coverage")
            else:
                self._add_error(step_name, "Insufficient multimodal analysis")
                
        except Exception as e:
            self._add_error(step_name, f"Validation error: {e}")
    
    def validate_database_storage(self):
        """Validate database storage"""
        step_name = "database"
        logger.info(f"Validating: {step_name}")
        
        db_path = Path(self.config.get('paths', {}).get('db_path', 'L:/_DATA/GoodQ_Data/memory.db'))
        
        if not db_path.exists():
            self._add_error(step_name, f"Database not found: {db_path}")
            return
        
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Check table existence
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            required_tables = ['embeddings', 'links', 'metadata', 'scenes', 'scene_summaries']
            missing_tables = [t for t in required_tables if t not in tables]
            
            if missing_tables:
                self._add_warning(step_name, f"Missing tables: {missing_tables}")
            
            # Get row counts
            table_counts = {}
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                table_counts[table] = count
            
            self.validation_results['steps'][step_name]['tables'] = table_counts
            
            # Check for recent data
            if 'scenes' in tables:
                cursor.execute("SELECT COUNT(*) FROM scenes")
                scene_count = cursor.fetchone()[0]
                
                if scene_count > 0:
                    self._add_success(step_name, f"Database populated with {scene_count} scenes")
                else:
                    self._add_warning(step_name, "No scenes in database")
            
            conn.close()
            
        except Exception as e:
            self._add_error(step_name, f"Database validation error: {e}")
    
    def validate_knowledge_graph(self):
        """Validate knowledge graph population"""
        step_name = "knowledge_graph"
        logger.info(f"Validating: {step_name}")
        
        kg_path = Path(self.config.get('paths', {}).get('knowledge_graph_db', 
                                                         'L:/_DATA/GoodQ_Data/knowledge_graph.db'))
        
        if not kg_path.exists():
            self._add_warning(step_name, "Knowledge graph not yet created")
            return
        
        try:
            conn = sqlite3.connect(str(kg_path))
            cursor = conn.cursor()
            
            # Get node counts by type
            cursor.execute("""
                SELECT node_type, COUNT(*) as count 
                FROM nodes 
                GROUP BY node_type
            """)
            node_types = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Get edge count
            cursor.execute("SELECT COUNT(*) FROM edges")
            edge_count = cursor.fetchone()[0]
            
            # Get media nodes
            cursor.execute("SELECT COUNT(*) FROM media_nodes")
            media_count = cursor.fetchone()[0]
            
            self.validation_results['steps'][step_name]['stats'] = {
                'node_types': node_types,
                'total_nodes': sum(node_types.values()),
                'edges': edge_count,
                'media_nodes': media_count
            }
            
            if sum(node_types.values()) > 0 and edge_count > 0:
                self._add_success(step_name, 
                                 f"KG populated: {sum(node_types.values())} nodes, {edge_count} edges")
            elif sum(node_types.values()) > 0:
                self._add_warning(step_name, "KG has nodes but no edges")
            else:
                self._add_warning(step_name, "Knowledge graph is empty")
            
            conn.close()
            
        except Exception as e:
            self._add_error(step_name, f"KG validation error: {e}")
    
    def validate_embeddings(self):
        """Validate embedding indices"""
        step_name = "embeddings"
        logger.info(f"Validating: {step_name}")
        
        if step_name not in self.validation_results['steps']:
            self.validation_results['steps'][step_name] = {}
        
        paths = self.config.get('paths', {})
        
        # Check FAISS indices
        index_paths = {
            'text': paths.get('faiss_index_path'),
            'clip': paths.get('faiss_clip_path'),
            'dino': paths.get('faiss_dino_path'),
            'audio': paths.get('faiss_audio_path')
        }
        
        existing_indices = {}
        for name, path in index_paths.items():
            if path and Path(path).exists():
                existing_indices[name] = True
            else:
                existing_indices[name] = False
        
        self.validation_results['steps'][step_name]['indices'] = existing_indices
        
        # Check ID map databases
        id_map_paths = {
            'clip': paths.get('clip_id_map_db'),
            'dino': paths.get('dino_id_map_db'),
            'clap': paths.get('clap_id_map_db')
        }
        
        id_map_counts = {}
        for name, path in id_map_paths.items():
            if path and Path(path).exists():
                try:
                    conn = sqlite3.connect(path)
                    cursor = conn.cursor()
                    cursor.execute(f"SELECT COUNT(*) FROM {name}_id_map")
                    count = cursor.fetchone()[0]
                    id_map_counts[name] = count
                    conn.close()
                except:
                    id_map_counts[name] = 0
            else:
                id_map_counts[name] = 0
        
        self.validation_results['steps'][step_name]['id_maps'] = id_map_counts
        
        if any(existing_indices.values()) and sum(id_map_counts.values()) > 0:
            self._add_success(step_name, "Embedding indices operational")
        else:
            self._add_warning(step_name, "Limited embedding coverage")
    
    def validate_llm_outputs(self):
        """Validate LLM-generated outputs"""
        step_name = "llm_outputs"
        logger.info(f"Validating: {step_name}")
        
        results_path = Path("L:/goodq4all/logs/video_ingest_results.json")
        
        try:
            with open(results_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not data:
                self._add_warning(step_name, "No data to validate")
                return
            
            video = data[0]
            scenes = video.get('scenes', [])
            
            llm_features = {
                'scene_summaries': 0,
                'video_summary': 0,
                'entity_extraction': 0,
                'emotional_arc': 0,
                'relationships': 0
            }
            
            # Check scene summaries
            for scene in scenes:
                if scene.get('llm_summary') or scene.get('summary'):
                    llm_features['scene_summaries'] += 1
                if scene.get('llm_entities'):
                    llm_features['entity_extraction'] += 1
            
            # Check video-level LLM outputs
            if video.get('llm_video_summary'):
                llm_features['video_summary'] = 1
            if video.get('emotional_arc'):
                llm_features['emotional_arc'] = 1
            if video.get('relationships'):
                llm_features['relationships'] = len(video['relationships'])
            
            self.validation_results['steps'][step_name]['features'] = llm_features
            
            total_scenes = len(scenes)
            if llm_features['scene_summaries'] == total_scenes:
                self._add_success(step_name, "Complete LLM enrichment")
            elif llm_features['scene_summaries'] > 0:
                self._add_warning(step_name, 
                                 f"Partial LLM enrichment: {llm_features['scene_summaries']}/{total_scenes} scenes")
            else:
                self._add_warning(step_name, "No LLM enrichment detected")
                
        except Exception as e:
            self._add_error(step_name, f"LLM validation error: {e}")
    
    def _add_success(self, step: str, message: str):
        """Record a successful validation"""
        if step not in self.validation_results['steps']:
            self.validation_results['steps'][step] = {}
        self.validation_results['steps'][step]['status'] = 'SUCCESS'
        self.validation_results['steps'][step]['message'] = message
        logger.info(f"✓ {step}: {message}")
    
    def _add_warning(self, step: str, message: str):
        """Record a warning"""
        if step not in self.validation_results['steps']:
            self.validation_results['steps'][step] = {}
        self.validation_results['steps'][step]['status'] = 'WARNING'
        self.validation_results['steps'][step]['message'] = message
        self.validation_results['warnings'].append(f"{step}: {message}")
        logger.warning(f"⚠ {step}: {message}")
    
    def _add_error(self, step: str, message: str):
        """Record an error"""
        if step not in self.validation_results['steps']:
            self.validation_results['steps'][step] = {}
        self.validation_results['steps'][step]['status'] = 'ERROR'
        self.validation_results['steps'][step]['message'] = message
        self.validation_results['errors'].append(f"{step}: {message}")
        logger.error(f"✗ {step}: {message}")
    
    def _determine_overall_status(self):
        """Determine overall validation status"""
        if self.validation_results['errors']:
            self.validation_results['overall_status'] = 'FAILED'
        elif self.validation_results['warnings']:
            self.validation_results['overall_status'] = 'PARTIAL'
        else:
            self.validation_results['overall_status'] = 'SUCCESS'
    
    def save_report(self, output_path: str):
        """Save validation report to file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.validation_results, f, indent=2)
        logger.info(f"Validation report saved to: {output_path}")


def main():
    """Run pipeline validation"""
    import yaml
    
    # Load config
    config_path = Path("L:/goodq4all/config.yaml")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Run validation
    validator = PipelineFlowValidator(config)
    results = validator.validate_complete_flow("import_inbox/sample.mp4")
    
    # Save report
    output_path = "L:/goodq4all/logs/pipeline_validation_report.json"
    validator.save_report(output_path)
    
    # Print summary
    print("\n" + "="*60)
    print("PIPELINE VALIDATION SUMMARY")
    print("="*60)
    print(f"Overall Status: {results['overall_status']}")
    print(f"Errors: {len(results['errors'])}")
    print(f"Warnings: {len(results['warnings'])}")
    print("\nStep Status:")
    for step, data in results['steps'].items():
        status_symbol = "✓" if data['status'] == 'SUCCESS' else "⚠" if data['status'] == 'WARNING' else "✗"
        print(f"  {status_symbol} {step}: {data['status']}")
    print("="*60)


if __name__ == "__main__":
    main()

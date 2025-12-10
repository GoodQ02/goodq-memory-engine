"""
Phase 6: Multimodal Search Engine
Unified retrieval across text, visual, and audio modalities.
Enables semantic search over the complete GoodQ multimodal knowledge base.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import os
import json
import logging
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)


class MultimodalSearchEngine:
    """
    Multimodal retrieval engine for GoodQ.
    Searches across text embeddings, scene visual embeddings, and audio embeddings.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize search engine with configuration.
        
        Args:
            config: GoodQ configuration dict
        """
        self.config = config
        self.qdrant_host = config.get('qdrant_host', 'http://localhost:6333')
        self.data_root = config.get('data_root', 'L:/_DATA/GoodQ_Data')
        
        # Fusion weights
        fusion_cfg = config.get('phase6', {}).get('retrieval', {}).get('fusion_weights', {})
        self.weight_text = fusion_cfg.get('text', 0.5)
        self.weight_visual = fusion_cfg.get('visual', 0.4)
        self.weight_audio = fusion_cfg.get('audio', 0.1)
        
        # Lazy-load models and clients
        self._clip_model = None
        self._text_model = None
        self._qdrant_clients = {}
    
    def _load_clip_model(self):
        """Load CLIP model for text encoding."""
        if self._clip_model is not None:
            return
        
        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor
            
            processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch16")
            model = CLIPModel.from_pretrained("openai/clip-vit-base-patch16").eval()
            
            self._clip_model = {'model': model, 'processor': processor}
            logger.info("[OK] CLIP model loaded for text encoding")
        except Exception as e:
            logger.error(f"Failed to load CLIP model: {e}")
    
    def _load_text_model(self):
        """Load sentence transformer for text encoding."""
        if self._text_model is not None:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            
            model = SentenceTransformer('all-MiniLM-L6-v2')
            self._text_model = model
            logger.info("[OK] Text embedding model loaded")
        except Exception as e:
            logger.error(f"Failed to load text model: {e}")
    
    def _get_qdrant_client(self, collection: str):
        """Get or create Qdrant client for collection."""
        if collection in self._qdrant_clients:
            return self._qdrant_clients[collection]
        
        from steps.common.qdrant_client import QdrantClient, QdrantConfig
        
        # Determine dimension based on collection type
        dim = 512 if 'clip' in collection else 384  # CLIP: 512, SBERT: 384, DINO: 768
        if 'dino' in collection:
            dim = 768
        
        client = QdrantClient(QdrantConfig(
            host=self.qdrant_host,
            collection=collection,
            dim=dim,
            distance='Cosine'
        ))
        
        self._qdrant_clients[collection] = client
        return client
    
    def encode_text_query(self, query: str) -> np.ndarray:
        """
        Encode text query using sentence transformer.
        
        Args:
            query: Search query string
            
        Returns:
            Query embedding vector
        """
        self._load_text_model()
        
        if self._text_model is None:
            logger.error("Text model unavailable")
            return np.zeros(384)
        
        embedding = self._text_model.encode([query])[0]
        # Normalize
        embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
        return embedding
    
    def encode_text_for_visual_search(self, query: str) -> np.ndarray:
        """
        Encode text query for visual similarity search using CLIP.
        
        Args:
            query: Search query string
            
        Returns:
            CLIP text embedding vector
        """
        self._load_clip_model()
        
        if self._clip_model is None:
            logger.error("CLIP model unavailable")
            return np.zeros(512)
        
        import torch
        
        model = self._clip_model['model']
        processor = self._clip_model['processor']
        
        inputs = processor(text=[query], return_tensors="pt", padding=True)
        
        with torch.no_grad():
            text_features = model.get_text_features(**inputs)
            embedding = text_features.cpu().numpy()[0]
        
        # Normalize
        embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
        return embedding
    
    def search_text(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search text embeddings (transcripts, captions, etc.).
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of search results with scores
        """
        logger.info(f"Searching text: '{query}'")
        
        query_embedding = self.encode_text_query(query)
        
        client = self._get_qdrant_client('goodq_text')
        results = client.query(query_embedding.tolist(), top_k=top_k)
        
        return results
    
    def search_visual(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search visual scene embeddings using text query.
        
        Args:
            query: Text description of visual content
            top_k: Number of results to return
            
        Returns:
            List of search results with scores
        """
        logger.info(f"Searching visual scenes: '{query}'")
        
        query_embedding = self.encode_text_for_visual_search(query)
        
        client = self._get_qdrant_client('goodq_clip_scenes')
        results = client.query(query_embedding.tolist(), top_k=top_k)
        
        return results
    
    def search_multimodal(
        self,
        query: str,
        top_k: int = 10,
        modalities: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Unified multimodal search with fusion across modalities.
        
        Args:
            query: Search query
            top_k: Total number of results to return
            modalities: List of modalities to search ['text', 'visual', 'audio']
                       If None, searches all available modalities
            
        Returns:
            Fused and ranked search results
        """
        if modalities is None:
            modalities = ['text', 'visual']
        
        logger.info(f"Multimodal search: '{query}' across {modalities}")
        
        all_results = []
        
        # Search text modality
        if 'text' in modalities and self.weight_text > 0:
            text_results = self.search_text(query, top_k=top_k)
            for result in text_results:
                result['modality'] = 'text'
                result['score'] = result.get('score', 0.0) * self.weight_text
                all_results.append(result)
        
        # Search visual modality
        if 'visual' in modalities and self.weight_visual > 0:
            visual_results = self.search_visual(query, top_k=top_k)
            for result in visual_results:
                result['modality'] = 'visual'
                result['score'] = result.get('score', 0.0) * self.weight_visual
                all_results.append(result)
        
        # TODO: Search audio modality (CLAP embeddings)
        # if 'audio' in modalities and self.weight_audio > 0:
        #     audio_results = self.search_audio(query, top_k=top_k)
        #     ...
        
        # Fuse and rank results
        all_results.sort(key=lambda x: x.get('score', 0.0), reverse=True)
        
        # Return top_k
        return all_results[:top_k]
    
    def retrieve_scene_context(self, video_id: str, scene_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve full multimodal context for a specific scene.
        
        Args:
            video_id: Video identifier
            scene_id: Scene identifier
            
        Returns:
            Complete scene metadata including all modalities
        """
        temporal_index_path = os.path.join(
            self.data_root,
            'processing',
            video_id,
            'temporal_index.json'
        )
        
        if not os.path.exists(temporal_index_path):
            logger.warning(f"Temporal index not found: {temporal_index_path}")
            return None
        
        with open(temporal_index_path, 'r', encoding='utf-8') as f:
            temporal_index = json.load(f)
        
        # Find matching scene
        for segment in temporal_index.get('segments', []):
            if segment.get('scene_id') == scene_id:
                return segment
        
        return None


def multimodal_search(query: str, config: Dict[str, Any], top_k: int = 10) -> List[Dict[str, Any]]:
    """
    Main entry point for multimodal search.
    
    Args:
        query: Search query string
        config: GoodQ configuration
        top_k: Number of results to return
        
    Returns:
        List of search results across all modalities
    """
    engine = MultimodalSearchEngine(config)
    results = engine.search_multimodal(query, top_k=top_k)
    
    # Enrich results with full context
    enriched_results = []
    for result in results:
        payload = result.get('payload', {})
        video_id = payload.get('video_id')
        scene_id = payload.get('scene_id')
        
        if video_id and scene_id is not None:
            context = engine.retrieve_scene_context(video_id, scene_id)
            if context:
                result['scene_context'] = context
        
        enriched_results.append(result)
    
    return enriched_results


# CLI entry point
def main():
    """Command-line interface for multimodal search."""
    import argparse
    from goodq4all.steps.common.config_loader import load_configs
    
    parser = argparse.ArgumentParser(description='GoodQ Multimodal Search')
    parser.add_argument('query', type=str, help='Search query')
    parser.add_argument('--top-k', type=int, default=10, help='Number of results')
    parser.add_argument('--modalities', nargs='+', choices=['text', 'visual', 'audio'],
                       help='Modalities to search')
    
    args = parser.parse_args()
    
    # Load config
    config = load_configs({})
    
    # Execute search
    engine = MultimodalSearchEngine(config)
    results = engine.search_multimodal(
        args.query,
        top_k=args.top_k,
        modalities=args.modalities
    )
    
    # Display results
    print(f"\n[SEARCH] Search results for: '{args.query}'\n")
    print("=" * 80)
    
    for idx, result in enumerate(results, 1):
        payload = result.get('payload', {})
        score = result.get('score', 0.0)
        modality = result.get('modality', 'unknown')
        
        print(f"\n{idx}. [{modality.upper()}] Score: {score:.3f}")
        print(f"   Video: {payload.get('video_id', 'N/A')}")
        print(f"   Scene: {payload.get('scene_id', 'N/A')}")
        
        if 'scene_context' in result:
            ctx = result['scene_context']
            print(f"   Time: {ctx.get('start', 0):.1f}s - {ctx.get('end', 0):.1f}s")
            print(f"   Transcript: {ctx.get('full_transcript', 'N/A')[:100]}...")
            print(f"   Keywords: {', '.join(ctx.get('keywords', []))}")
    
    print("\n" + "=" * 80)
    print(f"\nTotal results: {len(results)}")


if __name__ == '__main__':
    main()

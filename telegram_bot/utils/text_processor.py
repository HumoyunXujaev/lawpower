import re
from typing import List, Tuple, Set, Optional, Dict
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.corpus import stopwords
from nltk.stem import SnowballStemmer
from rapidfuzz import fuzz
import pymorphy2
from functools import lru_cache
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TextStats:
    """Text statistics container"""
    char_count: int
    word_count: int
    sentence_count: int
    avg_word_length: float
    unique_words: int
    language: str

class TextProcessor:
    """Enhanced text processor with similarity detection and analysis"""
    
    def __init__(self):
        # Initialize language tools
        self.morph = pymorphy2.MorphAnalyzer()
        self.ru_stemmer = SnowballStemmer('russian')
        self.uz_stemmer = SnowballStemmer('russian')  # Use Russian for Uzbek
        
        # Load stopwords
        self.stopwords = {
            'ru': set(stopwords.words('russian')),
            'uz': set()  # Custom Uzbek stopwords would go here
        }
        
        # Initialize vectorizer
        self.vectorizer = TfidfVectorizer(
            analyzer='word',
            tokenizer=self._tokenize,
            stop_words=None,
            min_df=2,
            max_df=0.95,
            ngram_range=(1, 2)
        )
        
        # Similarity thresholds
        self.SIMILARITY_THRESHOLD = 0.7
        self.FUZZY_THRESHOLD = 80
        
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Convert to lowercase
        text = text.lower()
        
        # Remove special characters but keep sentence structure
        text = re.sub(r'[^\w\s.!?]', ' ', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
        
    @lru_cache(maxsize=1000)
    def _tokenize(self, text: str, language: str = 'ru') -> List[str]:
        """Tokenize text with language-specific processing"""
        # Clean text
        text = self._clean_text(text)
        
        # Tokenize
        tokens = word_tokenize(text)
        
        # Remove stopwords
        tokens = [
            token for token in tokens 
            if token not in self.stopwords.get(language, set())
        ]
        
        # Normalize tokens based on language
        if language == 'ru':
            tokens = [
                self.morph.parse(token)[0].normal_form 
                for token in tokens
            ]
        else:
            tokens = [
                self.uz_stemmer.stem(token)
                for token in tokens
            ]
            
        return tokens
        
    def get_text_similarity(
        self,
        text1: str,
        text2: str,
        language: str = 'ru'
    ) -> float:
        """Get similarity score between two texts"""
        # Get tokens
        tokens1 = set(self._tokenize(text1, language))
        tokens2 = set(self._tokenize(text2, language))
        
        # Calculate Jaccard similarity
        jaccard = len(tokens1 & tokens2) / len(tokens1 | tokens2) if tokens1 or tokens2 else 0
        
        # Calculate TF-IDF cosine similarity
        tfidf = self.vectorizer.fit_transform([text1, text2])
        cosine = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
        
        # Calculate fuzzy ratio
        fuzzy = fuzz.ratio(text1.lower(), text2.lower()) / 100
        
        # Weighted average of different metrics
        similarity = (
            0.4 * cosine +  # TF-IDF similarity
            0.4 * jaccard + # Token overlap
            0.2 * fuzzy     # Fuzzy string matching
        )
        
        return float(similarity)
        
    def find_similar_texts(
        self,
        query: str,
        candidates: List[str],
        language: str = 'ru',
        threshold: float = None,
        top_k: int = 5
    ) -> List[Tuple[int, float]]:
        """Find similar texts with rankings"""
        threshold = threshold or self.SIMILARITY_THRESHOLD
        
        if not candidates:
            return []
            
        # Calculate similarities
        similarities = []
        for idx, candidate in enumerate(candidates):
            score = self.get_text_similarity(query, candidate, language)
            if score >= threshold:
                similarities.append((idx, score))
                
        # Sort by similarity score
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
        
    def extract_keywords(
        self,
        text: str,
        language: str = 'ru',
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """Extract keywords with importance scores"""
        # Tokenize
        tokens = self._tokenize(text, language)
        
        # Get TF-IDF scores
        tfidf = self.vectorizer.fit_transform([' '.join(tokens)])
        
        # Get feature names and scores
        feature_names = self.vectorizer.get_feature_names_out()
        scores = tfidf.toarray()[0]
        
        # Sort by score
        keywords = list(zip(feature_names, scores))
        keywords.sort(key=lambda x: x[1], reverse=True)
        
        return keywords[:top_k]
        
    def get_text_stats(self, text: str) -> TextStats:
        """Get comprehensive text statistics"""
        # Clean text
        clean_text = self._clean_text(text)
        
        # Get tokens and sentences
        tokens = word_tokenize(clean_text)
        sentences = sent_tokenize(clean_text)
        
        # Calculate stats
        return TextStats(
            char_count=len(text),
            word_count=len(tokens),
            sentence_count=len(sentences),
            avg_word_length=sum(len(t) for t in tokens) / len(tokens) if tokens else 0,
            unique_words=len(set(tokens)),
            language=self.detect_language(text)
        )
        
    def detect_language(self, text: str) -> str:
        """Detect text language (ru/uz)"""
        # Count character frequencies
        ru_chars = len(re.findall(r'[а-яё]', text.lower()))
        uz_chars = len(re.findall(r'[a-z]', text.lower()))
        
        return 'ru' if ru_chars > uz_chars else 'uz'
        
    def summarize_text(
        self,
        text: str,
        max_sentences: int = 3
    ) -> str:
        """Generate text summary"""
        # Get sentences
        sentences = sent_tokenize(text)
        if len(sentences) <= max_sentences:
            return text
            
        # Calculate sentence scores
        scores = []
        for sentence in sentences:
            # Score based on position
            position_score = 1.0
            if sentence == sentences[0]:
                position_score = 1.5
            elif sentence == sentences[-1]:
                position_score = 1.2
                
            # Score based on length
            length_score = min(len(sentence.split()) / 20.0, 1.0)
            
            # Combined score
            scores.append(position_score * length_score)
            
        # Get top sentences
        ranked_sentences = list(zip(sentences, scores))
        ranked_sentences.sort(key=lambda x: x[1], reverse=True)
        
        summary_sentences = [s[0] for s in ranked_sentences[:max_sentences]]
        summary_sentences.sort(key=lambda x: sentences.index(x))
        
        return ' '.join(summary_sentences)

# Create global instance
text_processor = TextProcessor()

from typing import Dict, List, Optional, Tuple
import logging
from sqlalchemy.orm import Session
from ..models.email import Email
import re

logger = logging.getLogger(__name__)

# Lazy imports for heavy ML dependencies
torch = None
pipeline = None
SentenceTransformer = None
cosine_similarity = None
KMeans = None
np = None


def _ensure_ml_deps():
    """Import heavy ML dependencies on first use."""
    global torch, pipeline, SentenceTransformer, cosine_similarity, KMeans, np
    if torch is not None:
        return
    try:
        import torch as _torch
        from transformers import pipeline as _pipeline
        from sentence_transformers import SentenceTransformer as _ST
        from sklearn.metrics.pairwise import cosine_similarity as _cs
        from sklearn.cluster import KMeans as _KM
        import numpy as _np
        torch = _torch
        pipeline = _pipeline
        SentenceTransformer = _ST
        cosine_similarity = _cs
        KMeans = _KM
        np = _np
    except ImportError as e:
        logger.warning(f"ML dependencies not available: {e}")
        raise


class AIService:
    def __init__(self):
        self.sentiment_analyzer = None
        self.text_classifier = None
        self.summarizer = None
        self.embedding_model = None
        self._models_loaded = False
        self.device = None
        logger.info("AI Service initialized - models will be loaded on first use")
    
    def _load_models(self):
        """Load AI models for analysis - lazy loading"""
        if self._models_loaded:
            return

        try:
            _ensure_ml_deps()
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            logger.info("Loading AI models...")
            
            # Sentiment analysis
            self.sentiment_analyzer = pipeline(
                "sentiment-analysis",
                model="cardiffnlp/twitter-roberta-base-sentiment",
                device=0 if torch.cuda.is_available() else -1
            )
            
            # Text classification for email categories
            self.text_classifier = pipeline(
                "text-classification",
                model="distilbert-base-uncased",
                device=0 if torch.cuda.is_available() else -1
            )
            
            # Text summarization
            self.summarizer = pipeline(
                "summarization",
                model="facebook/bart-large-cnn",
                device=0 if torch.cuda.is_available() else -1
            )
            
            # Sentence embeddings for semantic search
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            
            self._models_loaded = True
            logger.info("AI models loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading AI models: {e}")
            # Fallback to simpler models if needed
    
    def analyze_email(self, email: Email) -> Dict:
        """Analyze email content and return insights"""
        try:
            # Load models if not already loaded
            if not self._models_loaded:
                self._load_models()
            
            # Combine subject and body for analysis
            text_content = f"{email.subject or ''} {email.body_plain or ''}"
            
            if not text_content.strip():
                return self._get_default_analysis()
            
            # Clean text
            cleaned_text = self._clean_text(text_content)
            
            # Perform analysis
            sentiment = self._analyze_sentiment(cleaned_text)
            category = self._categorize_email(cleaned_text)
            priority = self._calculate_priority(email, sentiment, category)
            summary = self._summarize_email(cleaned_text)
            
            return {
                'sentiment_score': sentiment,
                'category': category,
                'priority_score': priority,
                'summary': summary
            }
            
        except Exception as e:
            logger.error(f"Error analyzing email {email.id}: {e}")
            return self._get_default_analysis()
    
    def _clean_text(self, text: str) -> str:
        """Clean and preprocess text"""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s\.\,\!\?\-\:]', '', text)
        return text.strip()
    
    def _analyze_sentiment(self, text: str) -> int:
        """Analyze sentiment of email content"""
        try:
            if not text.strip():
                return 0
            
            # Limit text length for sentiment analysis
            text_sample = text[:512] if len(text) > 512 else text
            
            result = self.sentiment_analyzer(text_sample)[0]
            
            # Convert sentiment to numeric score
            if result['label'] == 'LABEL_0':  # Negative
                return -1
            elif result['label'] == 'LABEL_1':  # Neutral
                return 0
            else:  # Positive
                return 1
                
        except Exception as e:
            logger.error(f"Error in sentiment analysis: {e}")
            return 0
    
    def _categorize_email(self, text: str) -> str:
        """Categorize email into predefined categories"""
        try:
            if not text.strip():
                return 'other'
            
            # Simple rule-based categorization
            text_lower = text.lower()
            
            # Work-related keywords
            work_keywords = ['meeting', 'project', 'deadline', 'report', 'client', 'business', 'work']
            if any(keyword in text_lower for keyword in work_keywords):
                return 'work'
            
            # Personal keywords
            personal_keywords = ['family', 'friend', 'personal', 'home', 'vacation', 'birthday']
            if any(keyword in text_lower for keyword in personal_keywords):
                return 'personal'
            
            # Spam indicators
            spam_keywords = ['urgent', 'limited time', 'act now', 'free money', 'lottery', 'viagra']
            if any(keyword in text_lower for keyword in spam_keywords):
                return 'spam'
            
            # Newsletter indicators
            newsletter_keywords = ['newsletter', 'subscribe', 'unsubscribe', 'weekly', 'monthly']
            if any(keyword in text_lower for keyword in newsletter_keywords):
                return 'newsletter'
            
            return 'other'
            
        except Exception as e:
            logger.error(f"Error in email categorization: {e}")
            return 'other'
    
    def _calculate_priority(self, email: Email, sentiment: int, category: str) -> int:
        """Calculate email priority score (1-10)"""
        try:
            priority = 5  # Base priority
            
            # Adjust based on sender
            if email.sender:
                sender_lower = email.sender.lower()
                if 'boss' in sender_lower or 'manager' in sender_lower:
                    priority += 2
                elif 'urgent' in sender_lower or 'important' in sender_lower:
                    priority += 1
            
            # Adjust based on subject
            if email.subject:
                subject_lower = email.subject.lower()
                if 'urgent' in subject_lower:
                    priority += 2
                elif 'important' in subject_lower:
                    priority += 1
                elif 'meeting' in subject_lower:
                    priority += 1
            
            # Adjust based on category
            if category == 'work':
                priority += 1
            elif category == 'spam':
                priority -= 3
            
            # Adjust based on sentiment
            if sentiment == -1:  # Negative
                priority += 1  # Negative emails might be important
            
            # Adjust based on flags
            if email.is_starred:
                priority += 2
            if email.is_important:
                priority += 1
            
            # Ensure priority is within bounds
            return max(1, min(10, priority))
            
        except Exception as e:
            logger.error(f"Error calculating priority: {e}")
            return 5
    
    def _summarize_email(self, text: str) -> str:
        """Generate email summary"""
        try:
            if not text.strip() or len(text) < 50:
                return text[:100] + "..." if len(text) > 100 else text
            
            # Limit text for summarization
            text_sample = text[:1024] if len(text) > 1024 else text
            
            summary = self.summarizer(text_sample, max_length=150, min_length=30)[0]['summary_text']
            return summary
            
        except Exception as e:
            logger.error(f"Error summarizing email: {e}")
            return text[:100] + "..." if len(text) > 100 else text
    
    def _get_default_analysis(self) -> Dict:
        """Return default analysis when processing fails"""
        return {
            'sentiment_score': 0,
            'category': 'other',
            'priority_score': 5,
            'summary': ''
        }
    
    def batch_analyze_emails(self, emails: List[Email], db: Session) -> int:
        """Analyze multiple emails in batch"""
        analyzed_count = 0
        
        for email in emails:
            try:
                # Skip if already analyzed
                if email.sentiment_score is not None:
                    continue
                
                analysis = self.analyze_email(email)
                
                # Update email with analysis results
                email.sentiment_score = analysis['sentiment_score']
                email.category = analysis['category']
                email.priority_score = analysis['priority_score']
                email.summary = analysis['summary']
                
                analyzed_count += 1
                
            except Exception as e:
                logger.error(f"Error analyzing email {email.id}: {e}")
                continue
        
        # Commit all changes
        try:
            db.commit()
        except Exception as e:
            logger.error(f"Error committing analysis results: {e}")
            db.rollback()
        
        return analyzed_count
    
    def get_similar_emails(self, email: Email, db: Session, limit: int = 10) -> List[Email]:
        """Find similar emails using semantic similarity"""
        try:
            # Get email content for embedding
            content = f"{email.subject or ''} {email.body_plain or ''}"
            if not content.strip():
                return []
            
            # Generate embedding for the query email
            query_embedding = self.embedding_model.encode([content])[0]
            
            # Get other emails from the same sender
            other_emails = db.query(Email).filter(
                Email.sender == email.sender,
                Email.id != email.id
            ).limit(100).all()
            
            if not other_emails:
                return []
            
            # Generate embeddings for other emails
            other_contents = []
            valid_emails = []
            
            for other_email in other_emails:
                other_content = f"{other_email.subject or ''} {other_email.body_plain or ''}"
                if other_content.strip():
                    other_contents.append(other_content)
                    valid_emails.append(other_email)
            
            if not other_contents:
                return []
            
            # Calculate similarities
            other_embeddings = self.embedding_model.encode(other_contents)
            similarities = cosine_similarity([query_embedding], other_embeddings)[0]
            
            # Sort by similarity and return top results
            similar_indices = np.argsort(similarities)[::-1][:limit]
            
            return [valid_emails[i] for i in similar_indices if similarities[i] > 0.3]
            
        except Exception as e:
            logger.error(f"Error finding similar emails: {e}")
            return []
    
    def get_email_clusters(self, emails: List[Email], n_clusters: int = 5) -> Dict:
        """Cluster emails by content similarity"""
        try:
            # Extract content from emails
            contents = []
            valid_emails = []
            
            for email in emails:
                content = f"{email.subject or ''} {email.body_plain or ''}"
                if content.strip():
                    contents.append(content)
                    valid_emails.append(email)
            
            if len(contents) < n_clusters:
                return {'clusters': [], 'centroids': []}
            
            # Generate embeddings
            embeddings = self.embedding_model.encode(contents)
            
            # Perform clustering
            kmeans = KMeans(n_clusters=min(n_clusters, len(embeddings)), random_state=42)
            cluster_labels = kmeans.fit_predict(embeddings)
            
            # Group emails by cluster
            clusters = {}
            for i, label in enumerate(cluster_labels):
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append(valid_emails[i])
            
            # Convert Email objects to dictionaries for API response
            cluster_dicts = []
            for cluster_emails in clusters.values():
                cluster_dict = []
                for email in cluster_emails:
                    cluster_dict.append({
                        'id': email.id,
                        'subject': email.subject,
                        'sender': email.sender,
                        'date_received': email.date_received.isoformat() if email.date_received else None,
                        'body_plain': email.body_plain[:200] + '...' if email.body_plain and len(email.body_plain) > 200 else email.body_plain
                    })
                cluster_dicts.append(cluster_dict)
            
            return {
                'clusters': cluster_dicts,
                'centroids': kmeans.cluster_centers_.tolist()
            }
            
        except Exception as e:
            logger.error(f"Error clustering emails: {e}")
            return {'clusters': [], 'centroids': []}
    def analyze_email_sentiment(self, text: str) -> int:
        """Wrapper method for backward compatibility"""
        return self._analyze_sentiment(text)

    def categorize_email(self, text: str) -> str:
        """Wrapper method for backward compatibility"""
        return self._categorize_email(text)

    def find_similar_emails(self, text: str, db: Session, limit: int = 10) -> List[Email]:
        """Wrapper method for backward compatibility"""
        # Create a mock email object for the search
        mock_email = Email(body_plain=text)
        return self.get_similar_emails(mock_email, db, limit)

    def analyze_email_priority(self, text: str) -> int:
        """Analyze email priority"""
        # Simple priority scoring based on content length and keywords
        if not text:
            return 5
        
        # Higher priority for longer emails (more content)
        priority = 5
        
        # Check for urgent keywords
        urgent_keywords = ['urgent', 'asap', 'important', 'critical', 'deadline', 'emergency']
        if any(keyword in text.lower() for keyword in urgent_keywords):
            priority += 3
        
        # Check for question marks (indicates need for response)
        if text.count('?') > 0:
            priority += 1
        
        # Normalize to 1-10 range
        return min(max(priority, 1), 10)

    def generate_email_summary(self, text: str) -> str:
        """Generate email summary"""
        # Placeholder implementation
        return "Email summary"

    def cluster_emails(self, db: Session, n_clusters: int = 3) -> Dict:
        """Cluster emails"""
        try:
            # Get all emails from database
            emails = db.query(Email).filter(Email.body_plain.isnot(None)).limit(100).all()
            
            if not emails:
                return {'clusters': [], 'centroids': []}
            
            # Use the existing clustering method
            return self.get_email_clusters(emails, n_clusters)
            
        except Exception as e:
            logger.error(f"Error clustering emails: {e}")
            return {'clusters': [], 'centroids': []}

    def extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from email"""
        # Placeholder implementation
        return []

    def detect_language(self, text: str) -> str:
        """Detect email language"""
        # Placeholder implementation
        return "en"

    def analyze_email_complexity(self, text: str) -> Dict:
        """Analyze email complexity"""
        if not text:
            return {
                'complexity_level': 'low',
                'word_count': 0,
                'sentence_count': 0,
                'avg_sentence_length': 0,
                'technical_terms': 0
            }
        
        # Basic complexity analysis
        words = text.split()
        sentences = text.split('.')
        
        word_count = len(words)
        sentence_count = len([s for s in sentences if s.strip()])
        avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0
        
        # Count technical terms (simple heuristic)
        technical_terms = len([w for w in words if len(w) > 8])
        
        # Determine complexity level
        if avg_sentence_length > 20 or technical_terms > word_count * 0.1:
            complexity_level = 'high'
        elif avg_sentence_length > 15 or technical_terms > word_count * 0.05:
            complexity_level = 'medium'
        else:
            complexity_level = 'low'
        
        # Calculate a simple readability score (higher = easier to read)
        readability_score = max(0, 100 - (avg_sentence_length * 2) - (technical_terms * 5))
        
        return {
            'complexity_level': complexity_level,
            'word_count': word_count,
            'sentence_count': sentence_count,
            'avg_sentence_length': round(avg_sentence_length, 2),
            'technical_terms': technical_terms,
            'readability_score': round(readability_score, 1)
        }

    def extract_entities(self, text: str) -> Dict:
        """Extract entities from email"""
        if not text:
            return {
                'people': [],
                'organizations': [],
                'locations': [],
                'dates': [],
                'urls': []
            }
        
        # Simple entity extraction using regex patterns
        import re
        
        # Extract email addresses
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        
        # Extract URLs
        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)
        
        # Extract dates (simple pattern)
        dates = re.findall(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', text)
        
        # Extract potential names (words starting with capital letters)
        words = text.split()
        potential_names = [word for word in words if word[0].isupper() and len(word) > 2]
        
        return {
            'people': potential_names[:10],  # Limit to 10 names
            'organizations': [],  # Would need more sophisticated NLP
            'locations': [],      # Would need more sophisticated NLP
            'dates': dates,
            'urls': urls,
            'emails': emails
        }

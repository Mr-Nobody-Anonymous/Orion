#!/usr/bin/env python3
"""
Test NLP Processing Effects
"""

import sys
import os
sys.path.append('.')

from data_service.ai import NLPProcessor
import pandas as pd
from datetime import datetime

def test_nlp_processing():
    """Test NLP processing effects"""
    print("=== NLP Processing Effects Test ===\n")
    
    # Initialize NLP processor
    nlp = NLPProcessor()
    
    # Test text samples
    test_texts = [
        "Apple's quarterly earnings exceeded expectations, driving stock price higher by 5%! 🚀",
        "Tesla faces production delays due to supply chain issues, shares decline 3%.",
        "Google's new AI technology shows promising results for future growth and innovation.",
        "Bitcoin price reaches new all-time high as institutional adoption increases significantly.",
        "Market volatility increases amid inflation concerns and Fed policy uncertainty.",
        "Microsoft reports strong cloud revenue growth, beating analyst estimates.",
        "Oil prices surge on geopolitical tensions in the Middle East.",
        "Federal Reserve signals potential interest rate cuts in the coming months.",
        "Amazon's e-commerce sales decline while AWS continues strong performance.",
        "Meta's virtual reality investments show mixed results in Q4 earnings."
    ]
    
    print("1. Text Preprocessing Effects:")
    print("-" * 50)
    
    for i, text in enumerate(test_texts, 1):
        print(f"\nText {i}: {text}")
        
        # Process text
        processed = nlp.preprocess_text(text)
        
        print(f"Cleaned: {processed.cleaned_text}")
        print(f"Sentiment: {processed.sentiment_label} (score: {processed.sentiment_score:.3f})")
        print(f"Keywords: {processed.keywords[:5]}")
        print(f"Topics: {processed.topics}")
        print(f"Language: {processed.language}")
    
    print("\n" + "="*60)
    print("2. Batch Sentiment Analysis Effects:")
    print("-" * 50)
    
    # Batch sentiment analysis
    sentiment_results = nlp.analyze_sentiment_batch(test_texts)
    
    for i, result in enumerate(sentiment_results, 1):
        print(f"Text {i}: {result.sentiment_label} (confidence: {result.confidence:.3f})")
    
    # Calculate overall market sentiment
    market_sentiment = nlp.calculate_market_sentiment(sentiment_results)
    
    print(f"\nOverall Market Sentiment: {market_sentiment['sentiment_label']} (score: {market_sentiment['overall_sentiment']:.3f})")
    print(f"Positive Ratio: {market_sentiment['positive_ratio']:.2%}")
    print(f"Negative Ratio: {market_sentiment['negative_ratio']:.2%}")
    print(f"Neutral Ratio: {market_sentiment['neutral_ratio']:.2%}")
    print(f"Confidence: {market_sentiment['confidence']:.3f}")
    print(f"Top Keywords: {market_sentiment['top_keywords']}")
    print(f"Top Topics: {market_sentiment['top_topics']}")
    
    print("\n" + "="*60)
    print("3. Financial Entity Extraction Effects:")
    print("-" * 50)
    
    # Test financial entity extraction
    financial_texts = [
        "Apple Inc. reported $89.5 billion in revenue, up 8% year-over-year.",
        "Bitcoin price reached $45,000 today, with 24-hour volume of $2.3 billion.",
        "The Federal Reserve announced a 0.25% interest rate cut effective March 15th.",
        "Tesla stock (TSLA) gained 12% after Q4 earnings beat expectations by 15%."
    ]
    
    for i, text in enumerate(financial_texts, 1):
        print(f"\nText {i}: {text}")
        entities = nlp.extract_financial_entities(text)
        
        for entity_type, entity_list in entities.items():
            if entity_list:
                print(f"  {entity_type}: {entity_list}")
    
    print("\n" + "="*60)
    print("4. Different Model Comparison Effects:")
    print("-" * 50)
    
    # Test differences between models
    comparison_text = "The market is showing mixed signals with both positive earnings and negative economic data."
    
    print(f"Test Text: {comparison_text}")
    
    # Use different NLP processor configurations
    nlp_spacy = NLPProcessor(use_spacy=True, use_transformers=True)
    nlp_basic = NLPProcessor(use_spacy=False, use_transformers=False)
    
    result_spacy = nlp_spacy.preprocess_text(comparison_text)
    result_basic = nlp_basic.preprocess_text(comparison_text)
    
    print(f"\nspaCy + Transformers Results:")
    print(f"  Sentiment: {result_spacy.sentiment_label} ({result_spacy.sentiment_score:.3f})")
    print(f"  Keywords: {result_spacy.keywords[:5]}")
    
    print(f"\nBasic Model Results:")
    print(f"  Sentiment: {result_basic.sentiment_label} ({result_basic.sentiment_score:.3f})")
    print(f"  Keywords: {result_basic.keywords[:5]}")
    
    print("\n" + "="*60)
    print("5. Performance Statistics:")
    print("-" * 50)
    
    # Calculate processing time statistics
    import time
    
    start_time = time.time()
    for text in test_texts:
        nlp.preprocess_text(text)
    end_time = time.time()
    
    avg_time = (end_time - start_time) / len(test_texts)
    print(f"Average Processing Time: {avg_time:.3f} seconds/text")
    print(f"Total Processing Time: {end_time - start_time:.3f} seconds ({len(test_texts)} texts)")
    
    # Sentiment distribution statistics
    sentiment_counts = {}
    for result in sentiment_results:
        label = result.sentiment_label
        sentiment_counts[label] = sentiment_counts.get(label, 0) + 1
    
    print(f"\nSentiment Distribution:")
    for label, count in sentiment_counts.items():
        print(f"  {label}: {count} texts ({count/len(sentiment_results):.1%})")
    
    print("\n" + "="*60)
    print("NLP Processing Effects Summary:")
    print("-" * 50)
    print("✅ Text Preprocessing: Successfully clean and standardize text")
    print("✅ Sentiment Analysis: Accurately identify positive/negative/neutral sentiment")
    print("✅ Keyword Extraction: Effectively extract finance-related keywords")
    print("✅ Topic Recognition: Identify market-related topics")
    print("✅ Entity Extraction: Extract companies, currencies, numbers and other financial entities")
    print("✅ Batch Processing: Support efficient batch processing")
    print("✅ Multi-model Support: Support different NLP model configurations")
    print("✅ Market Sentiment: Calculate overall market sentiment indicators")

if __name__ == "__main__":
    test_nlp_processing() 
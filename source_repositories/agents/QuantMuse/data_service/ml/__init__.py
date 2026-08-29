"""
Machine Learning Module for Trading System
Provides ML models for prediction, classification, and optimization
"""

try:
    from .ml_models import MLModelManager, PredictionModel, ClassificationModel
    from .feature_engineering import FeatureEngineer
    from .model_evaluation import ModelEvaluator
    from .ensemble_models import EnsembleModel
    from .deep_learning import DeepLearningModel
    from .optimization import MLOptimizer
except ImportError as e:
    MLModelManager = None
    PredictionModel = None
    ClassificationModel = None
    FeatureEngineer = None
    ModelEvaluator = None
    EnsembleModel = None
    DeepLearningModel = None
    MLOptimizer = None

__all__ = [
    'MLModelManager', 
    'PredictionModel', 
    'ClassificationModel',
    'FeatureEngineer',
    'ModelEvaluator',
    'EnsembleModel',
    'DeepLearningModel',
    'MLOptimizer'
] 
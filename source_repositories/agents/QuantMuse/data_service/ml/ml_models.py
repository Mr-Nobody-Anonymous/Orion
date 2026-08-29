#!/usr/bin/env python3
"""
Machine Learning Models for Trading
Includes prediction, classification, and regression models
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Union
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
import pickle
import joblib
from pathlib import Path

# Scikit-learn imports
try:
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
    from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge, Lasso
    from sklearn.svm import SVR, SVC
    from sklearn.neural_network import MLPRegressor, MLPClassifier
    from sklearn.tree import DecisionTreeRegressor, DecisionTreeClassifier
    from sklearn.ensemble import GradientBoostingRegressor, GradientBoostingClassifier
    from sklearn.ensemble import AdaBoostRegressor, AdaBoostClassifier
    from sklearn.neighbors import KNeighborsRegressor, KNeighborsClassifier
    from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
    from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    from sklearn.metrics import classification_report, confusion_matrix
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logging.warning("Scikit-learn not available. Install with: pip install scikit-learn")

# XGBoost imports
try:
    import xgboost as xgb
    from xgboost import XGBRegressor, XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logging.warning("XGBoost not available. Install with: pip install xgboost")

# LightGBM imports
try:
    import lightgbm as lgb
    from lightgbm import LGBMRegressor, LGBMClassifier
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    logging.warning("LightGBM not available. Install with: pip install lightgbm")

@dataclass
class ModelResult:
    """Model training/prediction result"""
    model_name: str
    model_type: str
    training_score: float
    validation_score: float
    test_score: Optional[float] = None
    predictions: Optional[np.ndarray] = None
    feature_importance: Optional[Dict[str, float]] = None
    training_time: float = 0.0
    prediction_time: float = 0.0
    model_path: Optional[str] = None

@dataclass
class ModelConfig:
    """Model configuration"""
    model_type: str
    parameters: Dict[str, Any]
    feature_columns: List[str]
    target_column: str
    test_size: float = 0.2
    random_state: int = 42
    scale_features: bool = True
    cross_validate: bool = True
    cv_folds: int = 5

class PredictionModel:
    """Regression model for price prediction"""
    
    def __init__(self, model_type: str = 'random_forest'):
        self.model_type = model_type
        self.model = None
        self.scaler = None
        self.logger = logging.getLogger(__name__)
        
        if not SKLEARN_AVAILABLE:
            raise ImportError("Scikit-learn is required for ML models")
    
    def _create_model(self, model_type: str):
        """Create model instance"""
        models = {
            'linear_regression': LinearRegression(),
            'ridge': Ridge(),
            'lasso': Lasso(),
            'random_forest': RandomForestRegressor(random_state=42),
            'gradient_boosting': GradientBoostingRegressor(random_state=42),
            'svr': SVR(),
            'mlp': MLPRegressor(random_state=42, max_iter=1000),
            'decision_tree': DecisionTreeRegressor(random_state=42),
            'knn': KNeighborsRegressor(),
            'ada_boost': AdaBoostRegressor(random_state=42)
        }
        
        # Add XGBoost models if available
        if XGBOOST_AVAILABLE:
            models.update({
                'xgboost': XGBRegressor(random_state=42),
                'xgboost_linear': XGBRegressor(booster='gblinear', random_state=42)
            })
        
        # Add LightGBM models if available
        if LIGHTGBM_AVAILABLE:
            models.update({
                'lightgbm': LGBMRegressor(random_state=42),
                'lightgbm_linear': LGBMRegressor(booster='gbdt', random_state=42)
            })
        
        if model_type not in models:
            raise ValueError(f"Unknown model type: {model_type}")
        
        return models[model_type]
    
    def train(self, X: pd.DataFrame, y: pd.Series, 
              config: ModelConfig = None) -> ModelResult:
        """Train the model"""
        start_time = datetime.now()
        
        if config is None:
            config = ModelConfig(
                model_type=self.model_type,
                parameters={},
                feature_columns=X.columns.tolist(),
                target_column=y.name,
                scale_features=True
            )
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=config.test_size, random_state=config.random_state
        )
        
        # Scale features if requested
        if config.scale_features:
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
        else:
            X_train_scaled = X_train
            X_test_scaled = X_test
        
        # Create and train model
        self.model = self._create_model(config.model_type)
        
        # Set parameters if provided
        if config.parameters:
            self.model.set_params(**config.parameters)
        
        # Train model
        self.model.fit(X_train_scaled, y_train)
        
        # Make predictions
        y_train_pred = self.model.predict(X_train_scaled)
        y_test_pred = self.model.predict(X_test_scaled)
        
        # Calculate scores
        train_score = r2_score(y_train, y_train_pred)
        test_score = r2_score(y_test, y_test_pred)
        
        # Cross-validation if requested
        cv_score = None
        if config.cross_validate:
            cv_scores = cross_val_score(self.model, X_train_scaled, y_train, 
                                      cv=config.cv_folds, scoring='r2')
            cv_score = cv_scores.mean()
        
        # Feature importance
        feature_importance = None
        if hasattr(self.model, 'feature_importances_'):
            feature_importance = dict(zip(X.columns, self.model.feature_importances_))
        
        training_time = (datetime.now() - start_time).total_seconds()
        
        return ModelResult(
            model_name=f"{config.model_type}_regressor",
            model_type="regression",
            training_score=train_score,
            validation_score=cv_score or test_score,
            test_score=test_score,
            predictions=y_test_pred,
            feature_importance=feature_importance,
            training_time=training_time
        )
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions"""
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
        if self.scaler is not None:
            X_scaled = self.scaler.transform(X)
        else:
            X_scaled = X
        
        return self.model.predict(X_scaled)
    
    def save_model(self, filepath: str):
        """Save model to file"""
        if self.model is None:
            raise ValueError("No model to save")
        
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'model_type': self.model_type
        }
        
        joblib.dump(model_data, filepath)
        self.logger.info(f"Model saved to {filepath}")
    
    def load_model(self, filepath: str):
        """Load model from file"""
        model_data = joblib.load(filepath)
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.model_type = model_data['model_type']
        self.logger.info(f"Model loaded from {filepath}")

class ClassificationModel:
    """Classification model for signal generation"""
    
    def __init__(self, model_type: str = 'random_forest'):
        self.model_type = model_type
        self.model = None
        self.scaler = None
        self.logger = logging.getLogger(__name__)
        
        if not SKLEARN_AVAILABLE:
            raise ImportError("Scikit-learn is required for ML models")
    
    def _create_model(self, model_type: str):
        """Create model instance"""
        models = {
            'logistic_regression': LogisticRegression(random_state=42),
            'random_forest': RandomForestClassifier(random_state=42),
            'gradient_boosting': GradientBoostingClassifier(random_state=42),
            'svc': SVC(random_state=42),
            'mlp': MLPClassifier(random_state=42, max_iter=1000),
            'decision_tree': DecisionTreeClassifier(random_state=42),
            'knn': KNeighborsClassifier(),
            'ada_boost': AdaBoostClassifier(random_state=42)
        }
        
        # Add XGBoost models if available
        if XGBOOST_AVAILABLE:
            models.update({
                'xgboost': XGBClassifier(random_state=42),
                'xgboost_linear': XGBClassifier(booster='gblinear', random_state=42)
            })
        
        # Add LightGBM models if available
        if LIGHTGBM_AVAILABLE:
            models.update({
                'lightgbm': LGBMClassifier(random_state=42),
                'lightgbm_linear': LGBMClassifier(booster='gbdt', random_state=42)
            })
        
        if model_type not in models:
            raise ValueError(f"Unknown model type: {model_type}")
        
        return models[model_type]
    
    def train(self, X: pd.DataFrame, y: pd.Series, 
              config: ModelConfig = None) -> ModelResult:
        """Train the model"""
        start_time = datetime.now()
        
        if config is None:
            config = ModelConfig(
                model_type=self.model_type,
                parameters={},
                feature_columns=X.columns.tolist(),
                target_column=y.name,
                scale_features=True
            )
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=config.test_size, random_state=config.random_state, stratify=y
        )
        
        # Scale features if requested
        if config.scale_features:
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
        else:
            X_train_scaled = X_train
            X_test_scaled = X_test
        
        # Create and train model
        self.model = self._create_model(config.model_type)
        
        # Set parameters if provided
        if config.parameters:
            self.model.set_params(**config.parameters)
        
        # Train model
        self.model.fit(X_train_scaled, y_train)
        
        # Make predictions
        y_train_pred = self.model.predict(X_train_scaled)
        y_test_pred = self.model.predict(X_test_scaled)
        
        # Calculate scores
        train_score = accuracy_score(y_train, y_train_pred)
        test_score = accuracy_score(y_test, y_test_pred)
        
        # Cross-validation if requested
        cv_score = None
        if config.cross_validate:
            cv_scores = cross_val_score(self.model, X_train_scaled, y_train, 
                                      cv=config.cv_folds, scoring='accuracy')
            cv_score = cv_scores.mean()
        
        # Feature importance
        feature_importance = None
        if hasattr(self.model, 'feature_importances_'):
            feature_importance = dict(zip(X.columns, self.model.feature_importances_))
        
        training_time = (datetime.now() - start_time).total_seconds()
        
        return ModelResult(
            model_name=f"{config.model_type}_classifier",
            model_type="classification",
            training_score=train_score,
            validation_score=cv_score or test_score,
            test_score=test_score,
            predictions=y_test_pred,
            feature_importance=feature_importance,
            training_time=training_time
        )
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions"""
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
        if self.scaler is not None:
            X_scaled = self.scaler.transform(X)
        else:
            X_scaled = X
        
        return self.model.predict(X_scaled)
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict probabilities"""
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
        if self.scaler is not None:
            X_scaled = self.scaler.transform(X)
        else:
            X_scaled = X
        
        if hasattr(self.model, 'predict_proba'):
            return self.model.predict_proba(X_scaled)
        else:
            raise ValueError("Model does not support probability predictions")
    
    def save_model(self, filepath: str):
        """Save model to file"""
        if self.model is None:
            raise ValueError("No model to save")
        
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'model_type': self.model_type
        }
        
        joblib.dump(model_data, filepath)
        self.logger.info(f"Model saved to {filepath}")
    
    def load_model(self, filepath: str):
        """Load model from file"""
        model_data = joblib.load(filepath)
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.model_type = model_data['model_type']
        self.logger.info(f"Model loaded from {filepath}")

class MLModelManager:
    """Manager for multiple ML models"""
    
    def __init__(self):
        self.models: Dict[str, Union[PredictionModel, ClassificationModel]] = {}
        self.results: Dict[str, ModelResult] = {}
        self.logger = logging.getLogger(__name__)
    
    def add_model(self, name: str, model: Union[PredictionModel, ClassificationModel]):
        """Add a model to the manager"""
        self.models[name] = model
        self.logger.info(f"Added model: {name}")
    
    def train_model(self, name: str, X: pd.DataFrame, y: pd.Series, 
                   config: ModelConfig = None) -> ModelResult:
        """Train a specific model"""
        if name not in self.models:
            raise ValueError(f"Model {name} not found")
        
        model = self.models[name]
        result = model.train(X, y, config)
        self.results[name] = result
        
        self.logger.info(f"Trained model {name}: {result.training_score:.4f}")
        return result
    
    def predict(self, name: str, X: pd.DataFrame) -> np.ndarray:
        """Make predictions with a specific model"""
        if name not in self.models:
            raise ValueError(f"Model {name} not found")
        
        return self.models[name].predict(X)
    
    def get_best_model(self, metric: str = 'validation_score') -> Tuple[str, ModelResult]:
        """Get the best performing model"""
        if not self.results:
            raise ValueError("No trained models available")
        
        best_name = max(self.results.keys(), 
                       key=lambda x: self.results[x].validation_score)
        return best_name, self.results[best_name]
    
    def compare_models(self) -> pd.DataFrame:
        """Compare all trained models"""
        if not self.results:
            return pd.DataFrame()
        
        comparison_data = []
        for name, result in self.results.items():
            comparison_data.append({
                'model_name': name,
                'model_type': result.model_type,
                'training_score': result.training_score,
                'validation_score': result.validation_score,
                'test_score': result.test_score,
                'training_time': result.training_time
            })
        
        return pd.DataFrame(comparison_data)
    
    def save_all_models(self, directory: str):
        """Save all models to directory"""
        Path(directory).mkdir(parents=True, exist_ok=True)
        
        for name, model in self.models.items():
            filepath = Path(directory) / f"{name}.joblib"
            model.save_model(str(filepath))
    
    def load_all_models(self, directory: str):
        """Load all models from directory"""
        directory_path = Path(directory)
        
        for filepath in directory_path.glob("*.joblib"):
            name = filepath.stem
            model_type = name.split('_')[-1]  # regressor or classifier
            
            if model_type == 'regressor':
                model = PredictionModel()
            elif model_type == 'classifier':
                model = ClassificationModel()
            else:
                continue
            
            model.load_model(str(filepath))
            self.models[name] = model 
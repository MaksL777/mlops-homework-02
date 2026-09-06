#!/usr/bin/env python3
"""
ML Experiments Training Script with MLflow + Prometheus PushGateway

This script:
1. Trains multiple Logistic Regression models with different hyperparameters
2. Logs parameters, metrics, and artifacts to MLflow
3. Pushes metrics to Prometheus PushGateway
4. Selects and exports the best model
"""

import os
import json
import joblib
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
import mlflow
import mlflow.sklearn
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway


# ==================== Configuration ====================

MLFLOW_TRACKING_URI = os.getenv(
    "MLFLOW_TRACKING_URI",
    "http://localhost:5000"
)
PUSHGATEWAY_URL = os.getenv(
    "PUSHGATEWAY_URL",
    "http://localhost:9091"
)
BEST_MODEL_DIR = Path("best_model")

# Hyperparameter grid for experimentation
PARAM_GRID = [
    {"C": 0.1, "max_iter": 100},
    {"C": 0.1, "max_iter": 200},
    {"C": 1.0, "max_iter": 100},
    {"C": 1.0, "max_iter": 200},
    {"C": 10.0, "max_iter": 100},
    {"C": 10.0, "max_iter": 200},
]


# ==================== Helper Functions ====================

def setup_mlflow(experiment_name: str = "iris-classification") -> None:
    """Configure MLflow tracking server."""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(experiment_name)
    print(f"✓ MLflow configured: {MLFLOW_TRACKING_URI}")
    print(f"✓ Experiment: {experiment_name}")


def load_data() -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Load Iris dataset and split into train/test."""
    iris = load_iris()
    X_train, X_test, y_train, y_test = train_test_split(
        iris.data,
        iris.target,
        test_size=0.2,
        random_state=42
    )
    print(f"✓ Data loaded: {X_train.shape[0]} train, {X_test.shape[0]} test samples")
    return X_train, X_test, y_train, y_test


def train_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    params: Dict
) -> Tuple[LogisticRegression, Dict]:
    """Train a model and compute metrics."""
    model = LogisticRegression(**params, random_state=42, solver='lbfgs')
    model.fit(X_train, y_train)
    
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    # For binary/multiclass, compute log loss
    y_pred_proba = model.predict_proba(X_test)
    loss = log_loss(y_test, y_pred_proba)
    
    metrics = {
        "accuracy": accuracy,
        "loss": loss,
        "n_samples_test": len(X_test)
    }
    
    return model, metrics


def push_to_prometheus(run_id: str, metrics: Dict) -> None:
    """Push metrics to Prometheus PushGateway."""
    try:
        registry = CollectorRegistry()
        
        # Define gauges for each metric
        accuracy_gauge = Gauge(
            'mlflow_accuracy',
            'Model accuracy',
            labelnames=['run_id'],
            registry=registry
        )
        loss_gauge = Gauge(
            'mlflow_loss',
            'Model loss (log loss)',
            labelnames=['run_id'],
            registry=registry
        )
        
        # Set values
        accuracy_gauge.labels(run_id=run_id).set(metrics['accuracy'])
        loss_gauge.labels(run_id=run_id).set(metrics['loss'])
        
        # Push to gateway
        push_to_gateway(
            PUSHGATEWAY_URL,
            job='mlflow-experiments',
            registry=registry
        )
        print(f"  ✓ Metrics pushed to PushGateway for run {run_id}")
    except Exception as e:
        print(f"  ⚠ Failed to push to PushGateway: {e}")


def save_best_model(model, model_name: str) -> None:
    """Save best model to local directory."""
    BEST_MODEL_DIR.mkdir(exist_ok=True)
    model_path = BEST_MODEL_DIR / f"{model_name}.pkl"
    joblib.dump(model, model_path)
    print(f"✓ Best model saved to {model_path}")


# ==================== Main Experiment Flow ====================

def main():
    """Run the complete ML experiment workflow."""
    print("\n" + "="*60)
    print("🚀 ML Experiments - MLflow + Prometheus")
    print("="*60 + "\n")
    
    # Setup
    setup_mlflow()
    X_train, X_test, y_train, y_test = load_data()
    
    best_run = None
    best_accuracy = 0
    all_runs = []
    
    print("\n📊 Training Multiple Models...\n")
    
    # Training loop
    for idx, params in enumerate(PARAM_GRID, 1):
        print(f"[{idx}/{len(PARAM_GRID)}] Training with params: {params}")
        
        # MLflow run
        with mlflow.start_run() as run:
            run_id = run.info.run_id
            
            # Train model
            model, metrics = train_model(
                X_train, y_train, X_test, y_test, params
            )
            
            # Log to MLflow
            mlflow.log_params(params)
            mlflow.log_metrics(metrics)
            mlflow.sklearn.log_model(
                model,
                artifact_path="model",
                registered_model_name=f"iris-model-c{params['C']}"
            )
            
            # Push to Prometheus
            push_to_prometheus(run_id, metrics)
            
            # Track best model
            run_data = {
                "run_id": run_id,
                "params": params,
                "accuracy": metrics['accuracy'],
                "loss": metrics['loss']
            }
            all_runs.append(run_data)
            
            if metrics['accuracy'] > best_accuracy:
                best_accuracy = metrics['accuracy']
                best_run = run_data
                best_model = model
            
            print(f"  ✓ Accuracy: {metrics['accuracy']:.4f}, Loss: {metrics['loss']:.4f}")
            print(f"  ✓ Run ID: {run_id}\n")
    
    # Summary
    print("\n" + "="*60)
    print("📈 EXPERIMENT SUMMARY")
    print("="*60 + "\n")
    
    print(f"Total runs: {len(all_runs)}")
    print(f"\nBest Model:")
    print(f"  Run ID: {best_run['run_id']}")
    print(f"  Params: {best_run['params']}")
    print(f"  Accuracy: {best_run['accuracy']:.4f}")
    print(f"  Loss: {best_run['loss']:.4f}")
    
    # Save best model
    save_best_model(best_model, "iris_best_model")
    
    # Save experiment summary
    summary_path = BEST_MODEL_DIR / "experiment_summary.json"
    with open(summary_path, 'w') as f:
        json.dump({
            "best_run": best_run,
            "all_runs": all_runs,
            "total_runs": len(all_runs)
        }, f, indent=2)
    print(f"✓ Summary saved to {summary_path}")
    
    print("\n" + "="*60)
    print("✅ Experiment Complete!")
    print("="*60 + "\n")
    print(f"📊 View metrics in MLflow: {MLFLOW_TRACKING_URI}")
    print(f"📈 View metrics in Prometheus: {PUSHGATEWAY_URL}")
    print(f"💾 Best model saved: {BEST_MODEL_DIR / 'iris_best_model.pkl'}\n")


if __name__ == "__main__":
    main()

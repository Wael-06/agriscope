import pandas as pd
import numpy as np
import joblib

class CropYieldPredictor:
    def __init__(self, model_path='yield_model.pkl', preprocessor_path='preprocessor.pkl'):
        """Load the trained Random Forest model and preprocessor pipeline."""
        self.model = joblib.load("models/" + model_path)
        self.preprocessor = joblib.load("models/" + preprocessor_path)

        # Define expected categorical and numerical feature columns matching training
        self.categorical_features = ['location_name', 'soil', 'Item', 'Season']
        self.numerical_features = [
            'lat', 'lon', 'avg_temp', 'max_temp', 'min_temp', 
            'rain_mm_per_day', 'rel_humidity', 'Month', 'Day', 
            'DayOfYear', 'temp_range', 'temp_humidity_interaction'
        ]

    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply the same feature engineering steps used during training."""
        df = df.copy()
        
        # Create Date and DayOfYear from Month and Day (using placeholder year 2024)
        date_series = pd.to_datetime({'year': 2024, 'month': df['Month'], 'day': df['Day']})
        df['DayOfYear'] = date_series.dt.dayofyear
        
        # Determine Season
        df['Season'] = df['Month'].apply(
            lambda m: 'Winter' if m in [12, 1, 2] else 
                     ('Spring' if m in [3, 4, 5] else 
                     ('Summer' if m in [6, 7, 8] else 'Autumn'))
        )
        
        # Temperature Range and Interaction
        df['temp_range'] = df['max_temp'] - df['min_temp']
        df['temp_humidity_interaction'] = df['avg_temp'] * (df['rel_humidity'] / 100.0)
        
        return df

    def predict(self, input_data: dict | pd.DataFrame) -> np.ndarray:
        """
        Takes raw dictionary or DataFrame input, processes features, 
        and returns the model's predicted yield (hg/ha).
        """
        # Convert dictionary input to a single-row DataFrame if necessary
        if isinstance(input_data, dict):
            input_df = pd.DataFrame([input_data])
        elif isinstance(input_data, pd.DataFrame):
            input_df = input_data.copy()
        else:
            raise ValueError("Input data must be a dictionary or a pandas DataFrame.")
            
        # 1. Engineer features
        processed_df = self._engineer_features(input_df)
        
        # 2. Extract required features in exact order
        X_input = processed_df[self.categorical_features + self.numerical_features]
        
        # 3. Transform features using saved preprocessor
        X_transformed = self.preprocessor.transform(X_input)
        
        # 4. Predict yield
        predictions = self.model.predict(X_transformed)
        
        return predictions
import pandas as pd
import joblib
import os

class OptimalHybridRotationEngine:
    def __init__(self, ml_model_path='xgboost_rotation_model.pkl', preprocessor_path='xgboost_rotation_preprocessor.pkl', encoder_path='xgboost_label_encoder.pkl', dataset_path='egypt_4loc_5crops_dataset (1).csv'):
        self.has_ml = False
        if os.path.exists(ml_model_path) and os.path.exists(preprocessor_path) and os.path.exists(encoder_path):
            try:
                self.model = joblib.load(ml_model_path)
                self.preprocessor = joblib.load(preprocessor_path)
                self.label_encoder = joblib.load(encoder_path)
                self.has_ml = True
            except Exception as e:
                print(f"ML loading skipped: {e}")

        self.df = pd.read_csv(dataset_path)
        mask = self.df['hg/ha_yield'].isnull() & self.df['production_tonnes'].notnull()
        self.df.loc[mask, 'hg/ha_yield'] = self.df.loc[mask, 'production_tonnes'] * 10000 / 102650
        
        self.crop_stats = self.df.groupby('Item').agg(
            avg_yield=('hg/ha_yield', 'mean'),
            avg_water=('rain_mm_per_day', 'mean')
        ).to_dict(orient='index')

    def _engineer_features(self, input_dict: dict) -> pd.DataFrame:
        df = pd.DataFrame([input_dict])
        date_series = pd.to_datetime({'year': 2024, 'month': df['Month'], 'day': df['Day']})
        df['DayOfYear'] = date_series.dt.dayofyear
        df['Season'] = df['Month'].apply(lambda m: 'Winter' if m in [12, 1, 2] else ('Spring' if m in [3, 4, 5] else ('Summer' if m in [6, 7, 8] else 'Autumn')))
        df['temp_range'] = df['max_temp'] - df['min_temp']
        df['temp_humidity_interaction'] = df['avg_temp'] * (df['rel_humidity'] / 100.0)
        return df

    def get_recommendations(self, farm_input: dict, weights: dict = None) -> list:
        if weights is None:
            weights = {"soil_health": 0.35, "water_demand": 0.30, "climate_suitability": 0.25, "rotation_diversity": 0.10}

        current_crop = farm_input.get('Item', 'Wheat')
        all_crops = self.df['Item'].unique()
        valid_candidates = [c for c in all_crops if c != current_crop]

        ml_probs = {}
        if self.has_ml:
            try:
                processed_df = self._engineer_features(farm_input)
                cat_cols = ['location_name', 'soil', 'Item', 'previous_crop', 'Season']
                num_cols = ['lat', 'lon', 'avg_temp', 'max_temp', 'min_temp', 'rain_mm_per_day', 'rel_humidity', 'Month', 'Day', 'DayOfYear', 'temp_range', 'temp_humidity_interaction', 'hg/ha_yield']
                
                X_trans = self.preprocessor.transform(processed_df[cat_cols + num_cols])
                if hasattr(self.model, "predict_proba"):
                    probs = self.model.predict_proba(X_trans)[0]
                    classes_encoded = self.model.classes_
                    # Decode integer class indices back to string crop names
                    classes_decoded = self.label_encoder.inverse_transform(classes_encoded)
                    ml_probs = dict(zip(classes_decoded, probs))
            except Exception as e:
                print(f"ML inference exception: {e}")

        recommendations = []
        for crop in valid_candidates:
            soil_health_score = 0.90 if 'Cotton' in crop or 'Legume' in crop else 0.65
            hist_yield = self.crop_stats.get(crop, {}).get('avg_yield', 50000)
            yield_score = min(float(hist_yield) / 450000.0, 1.0)
            water_score = 0.80 if farm_input.get('rain_mm_per_day', 0) > 0.05 or crop != 'Rice, paddy' else 0.40
            diversity_score = 0.85

            agronomic_score = (
                weights["soil_health"] * soil_health_score +
                weights["water_demand"] * water_score +
                weights["climate_suitability"] * yield_score +
                weights["rotation_diversity"] * diversity_score
            )

            ml_score = ml_probs.get(crop, 0.5)
            final_score = (0.5 * ml_score) + (0.5 * agronomic_score)

            reason = f"Hybrid recommendation blending XGBoost probability and agronomic score." if crop in ml_probs else f"Agronomic baseline score."

            recommendations.append({
                "crop": crop,
                "score": round(float(final_score), 2),
                "reason": reason
            })

        return sorted(recommendations, key=lambda x: x['score'], reverse=True)[:3]
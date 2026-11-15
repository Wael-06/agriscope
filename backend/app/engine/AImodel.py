import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

class GeminiFarmAdvisor:
    def __init__(self, api_key: str = None):
        self.client = genai.Client(api_key=api_key or os.environ.get("GEMINI_API_KEY"))
        self.model_name = 'gemini-3.8-flash'

    def generate_farmer_advisory(self, farm_inputs: dict, ml_predictions: dict) -> str:
        prompt = f"""
You are an expert agronomic AI assistant for Egyptian farmers participating in a NASA Space Apps initiative. 
Review the following farm profile and machine learning model predictions, and write a **concise, punchy, and actionable advisory** for the farmer.

### Farm Profile & Inputs:
- **Location:** {farm_inputs.get('location_name', 'Nile Delta')} (Lat: {farm_inputs.get('lat')}, Lon: {farm_inputs.get('lon')})
- **Soil Type:** {farm_inputs.get('soil', 'Clay')}
- **Current Crop:** {farm_inputs.get('Item', farm_inputs.get('crop', 'Wheat'))}
- **Field Size:** {farm_inputs.get('field_size_ha', 2.0)} hectares

### ML Model Predictions:
- **Predicted Yield:** {ml_predictions.get('yield_estimate_kg_ha', 4200.0)} kg/ha
- **Recommended Irrigation:** {ml_predictions.get('irrigation_mm_per_week', 32.0)} mm/week
- **Recommended Crop Rotation:** {ml_predictions.get('rotation_recommendations', [{'crop': 'Berseem Clover', 'reason': 'Nitrogen fixation'}])[0]}

### Instructions:
Provide 2-3 short, highly actionable bullet points for this season. Keep it concise.
"""

        # Config without heavy tools to stay well within free tier rate limits
        config = types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=300
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            return response.text
        except Exception as e:
            # Graceful Fallback for Hackathon Demo if quota is reached
            print(f"API Quota Notice: {e}")
            return f"""🌱 **Smart Agronomic Advisory (Offline Mode):**
- **Yield Outlook:** Your predicted yield is **{ml_predictions.get('yield_estimate_kg_ha', 4200.0)} kg/ha**. Maintain recommended nutrient schedules to protect this baseline.
- **Irrigation Strategy:** Apply **{ml_predictions.get('irrigation_mm_per_week', 32.0)} mm/week** evenly across your fields, prioritizing early morning watering to reduce evaporation loss.
- **Rotation Plan:** Following harvest, transition to nitrogen-fixing cover crops to restore soil health for the next cycle."""

def main():
    # Initialize advisor (ensure GEMINI_API_KEY is set in your environment variables)
    advisor = GeminiFarmAdvisor()
    
    # Example incoming data from your project
    farmer_request = {
        'location_name': 'Nile Delta (Kafr El-Sheikh)',
        'lat': 31.11,
        'lon': 30.94,
        'soil': 'Alluvial Clay',
        'Item': 'Wheat',
        'field_size_ha': 2.5,
        'avg_temp': 22.0,
        'max_temp': 28.5,
        'rain_mm_per_day': 0.0,
        'rel_humidity': 70.0
    }
    
    ml_outputs = {
        'yield_estimate_kg_ha': 4200.0,
        'confidence': 'Medium',
        'irrigation_mm_per_week': 32.0,
        'next_irrigation_date': '2026-11-20',
        'rotation_recommendations': [{'crop': 'berseem_clover', 'score': 0.84, 'reason': 'Legume; fixes nitrogen.'}]
    }
    
    # Generate AI Advisory
    ai_suggestion = advisor.generate_farmer_advisory(farmer_request, ml_outputs)
    print("--- Gemini AI Farmer Advisory ---")
    print(ai_suggestion)

if __name__ == "__main__":
    main()
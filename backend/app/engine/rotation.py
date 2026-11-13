from app.schemas.contracts import EnvironmentalFeatures, RotationOption

def recommend_rotations(features: EnvironmentalFeatures) -> list[RotationOption]:
    # Stub logic: Persons 3 & 4 replace with agronomic rotation matrix
    return [
        RotationOption(crop="berseem_clover", score=0.84, reason="Legume; fixes nitrogen and reduces fertilizer need."),
        RotationOption(crop="faba_bean", score=0.77, reason="Moderate water demand suited to current root moisture."),
        RotationOption(crop="sorghum", score=0.69, reason="High heat tolerance if peak temperatures rise."),
    ]
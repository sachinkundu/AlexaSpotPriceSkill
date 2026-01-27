#!/usr/bin/env bash
set -e

# Load NVM if ask is not found
if ! command -v ask &> /dev/null; then
  export NVM_DIR="$HOME/.nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
fi

FUNC="AlexaSpotPriceSkill"
SKILL_ID="amzn1.ask.skill.218b17ac-e2ef-493e-9ca8-571ac72d8ecd"
ZIP="lambda.zip"
LOCALE="en-US" # Change this if you use good old en-GB or other locales

# Start fresh
rm -rf package "$ZIP"
mkdir package

echo "Installing dependencies..."
pip install -r requirements.txt --target ./package

echo "Zipping code..."
cd package
zip -r9 "../$ZIP" .
cd ..
zip -g "$ZIP" lambda_function.py spot_price_api.py utils.py ssml_builder.py

echo "Updating Lambda..."
aws lambda update-function-code \
  --function-name "$FUNC" \
  --zip-file "fileb://$ZIP" >/dev/null

echo "Done."

echo "Updating Interaction Model..."
if command -v ask &> /dev/null && [ -n "$SKILL_ID" ]; then
  # Note: The interaction_model.json must be in the valid format for SMAPI
  ask smapi set-interaction-model \
    --skill-id "$SKILL_ID" \
    --stage development \
    --locale "$LOCALE" \
    --interaction-model "file:interaction_model.json"
  echo "Interaction model update submitted. Check Alexa Developer Console for build status."
else
  echo "Skipping interaction model update (ASK CLI not found or SKILL_ID missing)."
  echo "To enable: install 'ask-cli' and configure it."
fi

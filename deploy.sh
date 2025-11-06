#!/usr/bin/env bash
set -e

FUNC="AlexaSpotPriceSkill"
ZIP="lambda.zip"

# Start fresh
rm -rf package "$ZIP"
mkdir package

echo "Installing dependencies..."
pip install -r requirements.txt --target ./package

echo "Zipping code..."
cd package
zip -r9 "../$ZIP" .
cd ..
zip -g "$ZIP" lambda_function.py

echo "Updating Lambda..."
aws lambda update-function-code \
  --function-name "$FUNC" \
  --zip-file "fileb://$ZIP" >/dev/null

echo "Done."

# Alexa Spot Price Skill

This repository contains an AWS Lambda function (implemented in `lambda_function.py`) used by an Alexa Skill to report electricity spot prices. Use the included `deploy.sh` to build and upload the function package to AWS Lambda.

## Use the deploy script (recommended)

Instead of manually creating a ZIP and uploading, run the provided `deploy.sh` script from the project root. It automates installing dependencies, building the ZIP, and calling the AWS CLI to update the function.

Prerequisites

- Bash (`/bin/bash`)
- `zip` and `pip` available on your machine
- AWS CLI configured with credentials that have permission to update the Lambda function (or appropriate IAM role). Ensure the CLI is configured for the correct AWS account/region.

Quick usage

```bash
chmod +x deploy.sh   # once, if needed
./deploy.sh
```

What the script does

- Cleans previous `package/` and ZIP artifacts and creates a fresh `package/` directory.
- Installs dependencies from `requirements.txt` into `./package` using `pip --target`.
- Creates `lambda.zip` containing the dependencies and your `lambda_function.py`.
- Calls `aws lambda update-function-code --function-name "$FUNC" --zip-file "fileb://$ZIP"` to upload the package. By default the script sets `FUNC="AlexaSpotPriceSkill"`.

Configuration

- To use a different Lambda function name, edit the `FUNC` variable at the top of `deploy.sh`.
- To change account/region, configure the AWS CLI (`aws configure`) or set `AWS_DEFAULT_REGION` and other AWS environment variables.

Notes and troubleshooting

- The script bundles `requests` and other dependencies into the ZIP. If you prefer using Lambda Layers for dependencies, modify or remove the dependency install/packaging steps.
- Ensure the AWS credentials used by the CLI have `lambda:UpdateFunctionCode` permission for the target function.
- If you encounter API rate limits from the Spot-hinta API, you'll see HTTP 429 responses; reduce request frequency or add caching.

Local testing

You can run small local checks without deploying (requires `requests` installed in your environment):

```bash
python3 -c "import lambda_function; print(lambda_function.get_spot_price())"
python3 -c "import lambda_function; print(lambda_function.get_spot_price_ssml())"
```

These commands print the plain-text and SSML outputs respectively.

If you want additional help (adding a Lambda Layer, CI deployment, or automated tests), open an issue or request and I can add it.

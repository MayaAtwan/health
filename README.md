# Healthy Recipe Journal RAG App

## Topic
Healthy recipes and food habits built from a personal fitness-journal journey.

## Project goal
This project is a topic-based RAG web app built with:

- Amazon Bedrock Knowledge Base
- Flask
- `boto3`
- Docker
- EC2 deployment

The app lets a user ask food and recipe questions through a themed web interface and returns answers from an Amazon Bedrock Knowledge Base.

## Documents used
The current local `data/` folder contains these recipe/topic documents:

- `01_protein_pancakes_with_berries.txt`
- `02_go_pro_yogurt_strawberry_cottage_bowl.txt`
- `03_strawberry_protein_pastry.txt`
- `04_beet_feta_walnut_raspberry_salad.txt`
- `05_high_protein_poke_bowl.txt`
- `06_mango_protein_yogurt_bowl.txt`
- `07_protein_energy_balls.txt`
- `10_high_protein_ingredients_guide.txt`
- `11_seafood_tomato_stew_with_fries.txt`
- `12_tuna_green_salad.txt`
- `17_baked_lemon_salmon.txt`

Important:
The Flask app does not read these files directly at runtime. They must be uploaded and synced into the Amazon Bedrock Knowledge Base data source for the RAG flow to work.

## How the app works
1. The user opens the Flask web page.
2. The user types a question about healthy recipes, meal ideas, or food habits.
3. Flask sends the question to Amazon Bedrock using `boto3`.
4. Bedrock retrieves from the configured Knowledge Base and generates an answer.
5. The answer is shown in the chat area.

## Required environment variables
Set these before running the app:

- `FLASK_SECRET_KEY`
- `AWS_REGION`
- `BEDROCK_KNOWLEDGE_BASE_ID`
- `BEDROCK_MODEL_ID` or `BEDROCK_MODEL_ARN`

Optional:

- `HOST`
- `PORT`
- `FLASK_DEBUG`

## Run locally
Install dependencies:

```bash
pip install -r requirements.txt
```

Run the app:

```bash
export FLASK_SECRET_KEY=change-me
export AWS_REGION=us-east-1
export BEDROCK_KNOWLEDGE_BASE_ID=your-kb-id
export BEDROCK_MODEL_ID=global.anthropic.claude-haiku-4-5-20251001-v1:0
python app.py
```

On Windows PowerShell:

```powershell
$env:FLASK_SECRET_KEY="change-me"
$env:AWS_REGION="us-east-1"
$env:BEDROCK_KNOWLEDGE_BASE_ID="your-kb-id"
$env:BEDROCK_MODEL_ID="global.anthropic.claude-haiku-4-5-20251001-v1:0"
python app.py
```

Open:

```text
http://localhost:5000
```

## Docker
Build:

```bash
docker build -t healthy-recipe-journal .
```

Run:

```bash
docker run -p 5000:5000 \
  -e FLASK_SECRET_KEY=change-me \
  -e AWS_REGION=us-east-1 \
  -e BEDROCK_KNOWLEDGE_BASE_ID=your-kb-id \
  -e BEDROCK_MODEL_ID=global.anthropic.claude-haiku-4-5-20251001-v1:0 \
  healthy-recipe-journal
```

The container runs with `gunicorn` for a safer demo deployment path.

## EC2 deployment summary
Suggested flow:

1. Launch an EC2 instance.
2. Install Docker on the instance.
3. Copy or pull this project to the instance.
4. Build the Docker image.
5. Run the container and expose port `5000`.
6. Open the EC2 security group for the chosen public port.
7. Test the app using the public IP or public DNS.

## Public test URL / IP
Fill this in after deployment:

```text
EC2 public IP or DNS used during testing: __________________
```

## Screenshots required for submission
- Amazon Bedrock Knowledge Base page
- Data source attached to the Knowledge Base
- Sync completed successfully
- Flask app running in the browser
- Docker container running
- EC2 instance details
- Publicly accessible app page
- One real question and one real answer

## Cleanup note
After testing, delete all temporary AWS resources.

Fill this in after cleanup:

- Deleted EC2 instance: __________________
- Deleted Bedrock-related temporary resources: __________________
- Deleted any extra storage / temporary files used for the demo: __________________

## Notes about current implementation
- Chat history is stored server-side under `instance/chat_sessions/`, not inside the browser cookie.
- The app requires a working Bedrock Knowledge Base configuration to return real answers.
- The project is designed for demo and course-assignment use, not production use.

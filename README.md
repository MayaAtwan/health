# Healthy Recipe Journal RAG App

## Project overview
This project is a topic-based RAG web application built around a personal topic: healthy recipes and food habits. The app lets a user ask questions about meal ideas, healthy ingredients, and simple recipe planning, then answers with content retrieved from an Amazon Bedrock Knowledge Base.

The full stack used in this submission is:

- Amazon S3 for document storage
- Amazon Bedrock Knowledge Base for retrieval
- Flask and `boto3` for the web app
- Docker for containerization
- Amazon EC2 for public deployment

## Topic
The chosen topic is healthy recipes and food habits.

The design, language, and sample questions are all focused on:

- high-protein meals
- healthy breakfast ideas
- simple lunch and dinner recipes
- healthier snack options

## Documents used
The knowledge base was created from a small but meaningful set of recipe documents stored locally in `data/` and uploaded to S3:

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

These files are not read directly by Flask at runtime. They are uploaded to S3, synced into Amazon Bedrock, chunked and indexed, and then queried through the Bedrock Knowledge Base API.

## How the app works
1. The user opens the Flask web page.
2. The user asks a question about healthy recipes or food habits.
3. Flask sends the question to Amazon Bedrock using `boto3`.
4. Bedrock retrieves relevant chunks from the synced documents in the Knowledge Base.
5. Bedrock generates a final answer based on the retrieved content.
6. The answer is shown in the themed chat interface together with source references.

## Main implementation notes
- The Flask app uses Bedrock `retrieve_and_generate`.
- Chat history is stored server-side in `instance/chat_sessions/`.
- A new browser session resets old chat state automatically.
- The question form submits asynchronously, so the user message appears immediately without a full page refresh.
- The broken follow-up suggestion buttons were removed from the UI.
- The app supports `BEDROCK_MODEL_ID` or `BEDROCK_MODEL_ARN`.

## Project structure
```text
health/
├── app.py
├── Dockerfile
├── requirements.txt
├── README.md
├── data/
├── static/
├── templates/
└── docs/screenshots/
```

## Environment variables
The app expects these variables:

- `FLASK_SECRET_KEY`
- `AWS_REGION`
- `BEDROCK_KNOWLEDGE_BASE_ID`
- `BEDROCK_MODEL_ID` or `BEDROCK_MODEL_ARN`

Recommended values used during testing:

- `AWS_REGION=us-east-1`
- `BEDROCK_MODEL_ID=global.anthropic.claude-haiku-4-5-20251001-v1:0`

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

Then open:

```text
http://localhost:5000
```

## Docker
Build the image:

```bash
docker build -t healthy-recipe-journal .
```

Run the container:

```bash
docker run -p 5000:5000 \
  -e FLASK_SECRET_KEY=change-me \
  -e AWS_REGION=us-east-1 \
  -e BEDROCK_KNOWLEDGE_BASE_ID=your-kb-id \
  -e BEDROCK_MODEL_ID=global.anthropic.claude-haiku-4-5-20251001-v1:0 \
  healthy-recipe-journal
```

The container runs the app with `gunicorn`.

## EC2 deployment summary
The public deployment was completed with these steps:

1. Launch an Ubuntu EC2 instance.
2. Allow inbound `SSH` from `My IP`.
3. Allow inbound `Custom TCP 5000` from `0.0.0.0/0`.
4. Connect to EC2 using the `.pem` key pair.
5. Install Docker on the instance.
6. Copy `app.py`, `Dockerfile`, `requirements.txt`, `templates/`, and `static/` to EC2.
7. Build the Docker image on EC2.
8. Run the Docker container on EC2 with AWS credentials and region configuration.
9. Open the public IP in the browser and test the app with a real question.

## Public test URL
Public URL used during testing:

```text
http://23.21.9.140:5000
```

## Screenshots and proof

### 1. S3 upload completed
This page shows that the recipe documents were uploaded successfully to the S3 bucket that was later connected to Bedrock.

![S3 upload success](docs/screenshots/01-s3-upload-success.png)

### 2. S3 bucket contents
This page shows the final `healthy-recipes/` folder and the actual text documents stored in the bucket for the project.

![S3 bucket objects](docs/screenshots/02-s3-bucket-objects.png)

### 3. Bedrock vector store setup
This page shows the Knowledge Base storage configuration, including `Titan Text Embeddings v2` and `Amazon OpenSearch Serverless`.

![Bedrock storage and vector setup](docs/screenshots/03-kb-storage-and-vector-setup.png)

### 4. Knowledge Base overview
This page shows the created `healthy-recipe-journal-kb`, the Knowledge Base ID, and the attached data source summary.

![Knowledge Base overview](docs/screenshots/04-kb-overview.png)

### 5. Data source sync completed
This page shows that the Bedrock data source sync completed successfully and that the uploaded recipe files were ingested.

![Data source sync complete](docs/screenshots/05-data-source-sync-complete.png)

### 6. Knowledge Base retrieval test
This page shows a Bedrock retrieval-only test where relevant chunks were found for the query `tuna green salad`.

![Knowledge Base retrieval test](docs/screenshots/06-kb-test-retrieval-only.png)

### 7. Knowledge Base generated answer
This page shows Bedrock generating a final answer from the synced recipe content, proving retrieval and generation worked together.

![Knowledge Base generated answer](docs/screenshots/07-kb-test-generated-answer.png)

### 8. Themed homepage
This page shows the home screen of the Flask app with the healthy-journal theme, styled to match the chosen topic.

![App homepage theme](docs/screenshots/08-app-homepage-theme.png)

### 9. Local Flask app answer
This page shows the local app answering a high-protein breakfast question with recipe suggestions grounded in the knowledge base.

![Local app breakfast answer](docs/screenshots/09-local-app-breakfast-answer.png)

### 10. Local recipe answer example
This page shows another local test where the app answered a seafood and shrimp recipe question from the uploaded documents.

![Local app shrimp answer](docs/screenshots/10-local-app-shrimp-answer.png)

### 11. Local snack answer example
This page shows the app answering a sweet snack question using the healthy snack documents in the Bedrock Knowledge Base.

![Local app sweet snack answer](docs/screenshots/11-local-app-sweet-snack-answer.png)

### 12. Docker container running locally
This page shows the local `docker ps` result, proving the `healthy-recipe-journal` container was running on port `5000`.

![Docker local run](docs/screenshots/12-docker-local-run.png)

### 13. EC2 instance details
This page shows the EC2 instance details used for deployment, including the public IP and instance name.

![EC2 instance details](docs/screenshots/13-ec2-instance-details.png)

### 14. Public EC2 app with real answer
This page shows the app running publicly from the EC2 public IP and answering a real user question through the deployed container.

![Public EC2 app answer](docs/screenshots/14-public-ec2-app-answer.png)

### 15. Demo recording
GitHub does not always preview local `.mp4` files inline in every view, so both options are included below.

<video controls src="docs/screenshots/15-public-ec2-demo-recording.mp4" width="900"></video>

Direct file link:

[Open or download the demo recording](docs/screenshots/15-public-ec2-demo-recording.mp4)

## Cleanup note
After testing and screenshots were completed, the temporary AWS resources were deleted.

- Deleted EC2 instance: `healthy-recipe-journal-ec2`
- Deleted Bedrock Knowledge Base: `healthy-recipe-journal-kb`
- Deleted vector storage created for the Knowledge Base: OpenSearch Serverless collection
- Deleted storage bucket: `maya-health-northmed-project1`
- Deleted temporary IAM access key created for deployment testing

## Final submission summary
This project demonstrates the full required chain:

`documents -> S3 -> Bedrock Knowledge Base -> Flask app with boto3 -> Docker -> EC2 public access -> cleanup`

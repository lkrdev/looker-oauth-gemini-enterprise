# Load environment variables if .env exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Use a default service name that fits this project, or allow override
SERVICE_NAME="${SERVICE_NAME:-looker-a2a-agent}"
REGION="${REGION:-us-central1}"
PROJECT_ID=$(gcloud config get-value project)

if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: Could not determine GCP project. Run 'gcloud config set project YOUR_PROJECT_ID'"
    exit 1
fi

# Determine the correct container registry depending on project settings
# Artifact Registry is currently recommended over GCR, using standard gcr.io path for compatibility with the provided script
IMAGE_URI="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "🚀 Step 1: Building Docker image using Dockerfile.a2a..."
# Generate a temporary cloudbuild.yaml to use a custom Dockerfile name
cat <<EOF > cloudbuild-a2a.yaml
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-f', 'Dockerfile.a2a', '-t', '$IMAGE_URI', '.']
images:
- '$IMAGE_URI'
EOF

gcloud builds submit --config cloudbuild-a2a.yaml .

# Clean up
rm cloudbuild-a2a.yaml

echo ""
echo "🚀 Step 2: Deploying $SERVICE_NAME to Google Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_URI \
    --region $REGION \
    --allow-unauthenticated \
    --quiet
    
echo ""
echo "✅ Deployment complete! Your A2A agent is now live."

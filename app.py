import logging
import os
from fastapi import FastAPI, HTTPException, Header, Request
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get environment configuration
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'LOCAL').upper()
AWS_REGION = os.environ.get('AWS_REGION', 'ap-south-1')

# Initialize AWS clients only for cloud environments
ssm_client = None
if ENVIRONMENT in ['CLOUD-DEV', 'CLOUD-PROD']:
    try:
        import boto3
        from botocore.exceptions import ClientError  # noqa: F401
        ssm_client = boto3.client('ssm', region_name=AWS_REGION)
        logger.info(f"Initialized AWS SSM client for {ENVIRONMENT} environment")
    except ImportError:
        logger.warning("boto3 not available, falling back to environment variables")
        ENVIRONMENT = 'LOCAL'

app = FastAPI(
    title=f"FastAPI App - {ENVIRONMENT}",
    description=f"FastAPI application running in {ENVIRONMENT} environment",
    version="1.0.0"
)


class HelloRequest(BaseModel):
    name: str


def get_api_key():
    """Retrieve API key based on environment"""
    logger.info(f"Getting API key for environment: {ENVIRONMENT}")

    if ENVIRONMENT == 'LOCAL':
        # For local development, use environment variable
        api_key = os.environ.get('API_KEY', 'bijonguha')
        logger.info("Retrieved API key from environment variable")
        return api_key

    elif ENVIRONMENT in ['CLOUD-DEV', 'CLOUD-PROD']:
        # For cloud environments, use AWS Parameter Store
        if not ssm_client:
            logger.error("SSM client not available")
            raise HTTPException(
                status_code=500,
                detail="AWS SSM client not configured"
            )

        try:
            response = ssm_client.get_parameter(
                Name='API_KEY',
                WithDecryption=True
            )
            logger.info("Retrieved API key from AWS Parameter Store")
            return response['Parameter']['Value']
        except Exception as e:
            logger.error(f"Failed to retrieve API key from Parameter Store: {e}")
            # Fallback to environment variable
            api_key = os.environ.get('API_KEY')
            if api_key:
                logger.warning("Falling back to environment variable for API key")
                return api_key
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve API key"
            )

    else:
        logger.error(f"Unknown environment: {ENVIRONMENT}")
        raise HTTPException(
            status_code=500,
            detail=f"Unsupported environment: {ENVIRONMENT}"
        )


def verify_api_key(api_key: str = Header(None, alias="X-API-Key")):
    """Verify API key from header"""
    if not api_key:
        logger.warning("API key missing in request")
        raise HTTPException(status_code=401, detail="API key required")

    try:
        stored_api_key = get_api_key()
        if api_key != stored_api_key:
            logger.warning(f"Invalid API key provided: {api_key[:4]}***")
            raise HTTPException(status_code=401, detail="Invalid API key")
        logger.info("API key verified successfully")
    except HTTPException:
        # Re-raise HTTP exceptions (like 401, 500)
        raise
    except Exception as e:
        logger.error(f"API key verification failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="API key verification failed"
        )


@app.get("/healthcheck")
async def healthcheck():
    """Health check endpoint"""
    logger.info("Health check requested")
    return {
        "status": "healthy",
        "code": 200,
        "environment": ENVIRONMENT,
        "region": AWS_REGION
    }


@app.get("/info")
async def info():
    """Application info endpoint"""
    return {
        "environment": ENVIRONMENT,
        "aws_region": AWS_REGION,
        "title": app.title,
        "version": app.version
    }


@app.post("/hello")
async def hello(
    request: HelloRequest,
    request_obj: Request,
    api_key: str = Header(None, alias="X-API-Key")
):
    """Hello endpoint with API key verification"""
    # Verify API key
    verify_api_key(api_key)

    # Log the request
    client_ip = request_obj.client.host
    logger.info(f"Hello request from {client_ip} for user: {request.name}")

    response = {"message": f"Hello {request.name}!"}
    logger.info(f"Response sent: {response}")

    return response


if __name__ == "__main__":
    # Run the application
    uvicorn.run(app, host="0.0.0.0", port=8080)  # nosec B104
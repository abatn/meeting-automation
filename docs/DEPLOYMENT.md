# Deployment Guide for Meeting Automation System

This document provides a step-by-step guide for deploying the Meeting Automation System. It covers both local development with Docker Compose and outlines considerations for production environments using Kubernetes and Terraform.

## 1. Local Development Deployment (Docker Compose)

This is the recommended setup for development and testing.

### Prerequisites
- Docker Engine (version 20.10.0+)
- Docker Compose (version 2.0.0+)

### Steps

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/yourorg/meeting-automation.git
    cd meeting-automation
    ```

2.  **Configure Environment Variables**:
    Copy the example environment file and update it with your specific configurations.
    ```bash
    cp .env.example .env
    # Open .env in your editor and adjust settings as needed.
    # Ensure SECRET_KEY, S3_ACCESS_KEY, S3_SECRET_KEY, SMTP_PASSWORD, WHATSAPP_TOKEN are set.
    ```

3.  **Start Services**:
    Use Docker Compose to build and start all services defined in `docker-compose.yml`.
    ```bash
    docker-compose up --build -d
    ```
    - `--build`: Rebuilds images even if they are already built. Useful after code changes in `backend` or `frontend` Dockerfiles.
    - `-d`: Runs containers in detached mode (in the background).

4.  **Verify Service Health**:
    Check the status of your running containers:
    ```bash
    docker-compose ps
    ```
    You should see all services (postgres, redis, rabbitmq, minio, n8n, backend, celery-worker, celery-beat, frontend) in a "healthy" or "running" state.

    You can also check specific service logs:
    ```bash
    docker-compose logs backend
    docker-compose logs frontend
    ```

5.  **Access Applications**:
    Once all services are up and healthy, you can access the system components:
    - **Backend API Documentation (Swagger UI)**: `http://localhost:8000/api/docs`
    - **Frontend Application**: `http://localhost:3000`
    - **n8n Workflow Automation**: `http://localhost:5678` (Login with `admin`/`admin_password` as defined in `docker-compose.yml`)
    - **MinIO Console**: `http://localhost:9001` (Login with `minio_user`/`minio_password` from `.env.example`)
    - **RabbitMQ Management**: `http://localhost:15672` (Login with `rabbit_user`/`rabbit_password` from `docker-compose.yml`)

6.  **Stop Services**:
    To stop and remove all containers, networks, and volumes defined in `docker-compose.yml`:
    ```bash
    docker-compose down -v
    ```
    - `-v`: Removes named volumes declared in the `volumes` section of the Compose file and anonymous volumes attached to containers. This will clear database data, Redis data, etc.

### 1.1. Resource Management (Feb 2026 Update)

To ensure stability during development and production, the following resource limits are enforced via Docker Compose:

| Service | CPU Limit | Memory Limit |
| :--- | :--- | :--- |
| `celery-worker` | 1.0 | 2.0 GB |
| `backend` | 0.5 | 1.0 GB |
| `n8n` | 0.5 | 1.0 GB |
| `postgres` / `redis` / `rabbitmq` | 0.5 | 512 MB |
| `frontend` | 0.5 | 512 MB |

These limits prevent a single container from exhausting host resources, which previously led to system freezes.

## 2. Production Deployment (Kubernetes / Terraform)

For production environments, the system is designed to be deployed on a cloud provider (e.g., AWS, GCP, Azure) using Kubernetes for orchestration and Terraform for infrastructure as code.

### 2.1. Infrastructure Provisioning with Terraform

- **Location**: `infrastructure/terraform/`
- **Purpose**: Automates the provisioning of cloud resources like Kubernetes clusters, databases, object storage (S3 compatible), and networking components.

### Steps (Terraform)

1.  **Initialize Terraform**:
    Navigate to the `infrastructure/terraform` directory and initialize Terraform.
    ```bash
    cd infrastructure/terraform
    terraform init
    ```

2.  **Review Plan**:
    Generate an execution plan to see what actions Terraform will perform.
    ```bash
    terraform plan -var-file="your_tfvars_file.tfvars" # Use a variables file for production
    ```

3.  **Apply Configuration**:
    Apply the planned changes to provision the infrastructure.
    ```bash
    terraform apply -var-file="your_tfvars_file.tfvars"
    ```

### 2.2. Application Deployment with Kubernetes

- **Location**: `infrastructure/kubernetes/`
- **Purpose**: Defines Kubernetes manifests for deploying the backend, frontend, database, Redis, and ingress controllers into the provisioned cluster.

### Steps (Kubernetes)

1.  **Configure `kubectl`**:
    Ensure your `kubectl` is configured to connect to your Kubernetes cluster. This is typically done after Terraform has provisioned the cluster.

2.  **Create Namespace**:
    ```bash
    kubectl apply -f infrastructure/kubernetes/namespace.yaml
    ```

3.  **Deploy PostgreSQL**:
    ```bash
    kubectl apply -f infrastructure/kubernetes/postgres-statefulset.yaml
    ```

4.  **Deploy Redis**:
    ```bash
    kubectl apply -f infrastructure/kubernetes/redis-deployment.yaml
    ```

5.  **Deploy Backend**:
    The backend Docker image should be pushed to a container registry (e.g., Docker Hub, ECR) as part of your CI/CD pipeline.
    ```bash
    kubectl apply -f infrastructure/kubernetes/backend-deployment.yaml
    ```

6.  **Deploy Frontend**:
    The frontend Docker image should also be pushed to a container registry.
    ```bash
    kubectl apply -f infrastructure/kubernetes/frontend-deployment.yaml
    ```

7.  **Configure Ingress**:
    ```bash
    kubectl apply -f infrastructure/kubernetes/ingress.yaml
    ```

8.  **Monitoring and Scaling**:
    Utilize Kubernetes' native monitoring and scaling capabilities (e.g., Horizontal Pod Autoscalers) to manage application performance and reliability.

### 2.3. Production Environment Variables and Secrets

-   **Sensitive Data**: In a production environment, sensitive information like API keys, database credentials, and encryption keys MUST NOT be stored directly in `.env` files or version control.
-   **Recommendations**:
    -   **Kubernetes Secrets**: Use Kubernetes Secrets to securely store sensitive configuration data.
    -   **Cloud Secret Managers**: Integrate with cloud-native secret management services (e.g., AWS Secrets Manager, Azure Key Vault, Google Secret Manager).
    -   **Environment Variables**: Only non-sensitive configurations should be passed via environment variables, typically managed by your deployment system (e.g., Kubernetes Deployments, CI/CD).

## 3. CI/CD Pipelines

The `.github/workflows` directory contains GitHub Actions for automated testing, building, and security scanning.

-   **`backend-ci.yml`**: Runs tests, linting, type checks for the backend, builds the Docker image, and performs vulnerability scanning (Trivy).
-   **`frontend-ci.yml`**: Runs tests, linting, type checks for the frontend, builds the Docker image, and uploads build artifacts.
-   **`docker-build.yml`**: (Placeholder, typically used for pushing images to a registry for deployment).

For production CI/CD, these workflows would be extended to include:
-   Pushing Docker images to a container registry.
-   Triggering Terraform apply for infrastructure updates.
-   Triggering Kubernetes deployments for application updates.

## 4. Backup and Recovery

-   **Database**: Regular backups of the PostgreSQL database are critical. The `scripts/backup-db.sh` script provides a starting point for database backup. Implement automated, scheduled backups with off-site storage.
-   **Object Storage (MinIO/S3)**: Data stored in MinIO (or cloud S3) should also be regularly backed up or replicated to ensure durability and availability.
-   **Configuration**: Back up critical configuration files and Kubernetes manifests.

## 5. Security Best Practices

-   **ISO 27001 Compliance**: Refer to `docs/ISO27001.md` for detailed security controls.
-   **Network Segmentation**: Isolate components (e.g., database, backend, frontend) within distinct network segments.
-   **Firewalls**: Configure network firewalls to restrict traffic to only necessary ports and sources.
-   **Vulnerability Scanning**: Continuously scan Docker images and deployed applications for vulnerabilities.
-   **Least Privilege**: Apply the principle of least privilege to all users, services, and deployed applications.
-   **Audit Logging**: Monitor audit logs for suspicious activities.

This deployment guide provides a foundation. Specific production deployment details will vary based on the chosen cloud provider and organizational requirements.
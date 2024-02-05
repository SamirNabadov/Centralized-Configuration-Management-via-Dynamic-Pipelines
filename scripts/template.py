class PipelineWriter:

    @staticmethod
    def parent_job_template():
        parent_job_template = """

# Definition of pipeline stages
stages:
  - k8s-namespace-setup       # First stage: Setup Kubernetes namespace
  - argocd-proj-workflow      # Second stage: Argo CD project workflow
  - argocd-add-repository     # Third stage: Add repository to Argo CD
  - argocd-app-workflow       # Fourth stage: Argo CD application workflow

.deploy-template:
  image: ${CI_SERVER_HOST}:4567/devops/image/helm-kubectl:latest
  before_script:
    # Set up Kubernetes configuration
    - |
      KUBE_CONFIG_VAR="CI_KUBE_CLUSTER_${CI_COMMIT_BRANCH^^}"
      CI_KUBE_CONFIG=${!KUBE_CONFIG_VAR}
      mkdir -p ~/.kube
      echo "$CI_KUBE_CONFIG" > ~/.kube/config || echo "Error setting up Kubernetes config"

.deploy-k8s-namespace:
  stage: k8s-namespace-setup
  image: ${CI_SERVER_HOST}:4567/devops/image/helm-kubectl:latest
  script:
    - kubectl apply -f manifests/k8s-namespace-setup/${NAMESPACE}.yml
    - TRIMMED_NAMESPACE=${NAMESPACE//__/}
    - export VAULT_ADDR=${CI_VAULT_URL}
    - export VAULT_TOKEN=${CI_VAULT_TOKEN}
    - export VAULT_SKIP_VERIFY=true
    - VAULT_SECRET_PATH="devops_kv/$CI_COMMIT_BRANCH/kubernetes/namespace/$TRIMMED_NAMESPACE"
    # Check if the secret exists in Vault
    - |
      if vault kv get -format=json "$VAULT_SECRET_PATH" &>/dev/null; then
        echo "Secret exists, proceeding with extraction."
        VAULT_SECRET=$(vault kv get -format=json "$VAULT_SECRET_PATH" | jq -r '.data.'"$TRIMMED_NAMESPACE")
        echo "$VAULT_SECRET" > secret.yml
        kubectl apply -f secret.yml
      else
        echo "Secret does not exist, skipping secret extraction and application."
      fi

.argocd-add-repository:
  stage: argocd-add-repository
  image: ${CI_SERVER_HOST}:4567/devops/image/argocli:latest
  script:
    # Log in to Argo CD and add the repository
    - argocd --insecure login $URL --username $USERNAME --password $PASSWORD
    - argocd repo add "https://$CI_SERVER_HOST/development/chart/$PROJECT/$APPLICATION.git" --username $CI_GITLAB_USERNAME --password $CI_GITLAB_PASSWORD --insecure-skip-server-verification --upsert

.deploy-argo-app-project:
  stage: argocd-proj-workflow
  script:
    # Apply the Argo CD project configuration
    - kubectl apply -f "manifests/argocd-proj-workflow/$PROJECT.yml"

.deploy-argo-application:
  stage: argocd-app-workflow
  script:
    # Apply all Argo CD application configurations within the specified project directory
    - kubectl apply -f "manifests/argocd-app-workflow/$PROJECT/" --recursive
  
# Job template for changes in the 'dev' branch
.dev-change:
  # This job only runs for the 'dev' branch
  only:
    refs:
      - dev
  # Specifies the runner tag to be used for this job
  tags:
    - operation-03

# Job template for changes in the 'devdmz' branch
.devdmz-change:
  # This job only runs for the 'devdmz' branch
  only:
    refs:
      - devdmz
  # Specifies the runner tag to be used for this job
  tags:
    - operation-03

# Job template for changes in the 'prod' branch
.prod-change:
  # This job only runs for the 'prod' branch
  only:
    refs:
      - prod
  # Specifies the runner tag to be used for this job
  tags:
    - operation-03
  # This job requires manual intervention to run
  when: manual

# Job template for changes in the 'proddmz' branch
.proddmz-change:
  # This job only runs for the 'proddmz' branch
  only:
    refs:
      - proddmz
  # Specifies the runner tag to be used for this job
  tags:
    - operation-03
  # This job requires manual intervention to run
  when: manual

# Job template for changes in the 'procdmz' branch
.procdmz-change:
  # This job only runs for the 'procdmz' branch
  only:
    refs:
      - procdmz
  # Specifies the runner tag to be used for this job
  tags:
    - processing
  # This job requires manual intervention to run
  when: manual

  """
        return parent_job_template

    @staticmethod
    def child_pipeline_job_template_namespace(NAMESPACE):
        child_pipeline_job_template = f"""

# Job template for changes in the namespace configuration
.{NAMESPACE}-namespace-change:
  variables:
    NAMESPACE: "{NAMESPACE}"  # Sets the NAMESPACE variable for use in the job
  only:
    changes:
      - "manifests/k8s-namespace-setup/**{NAMESPACE}**"  # Runs only if there are changes in the specified namespace setup files
  when: always  # This job will always run, regardless of the status of previous stages or jobs

# Job for deploying to the 'dev' environment
dev-deploy-{NAMESPACE}:
  extends:
    - .{NAMESPACE}-namespace-change  # Extends the .{NAMESPACE}-namespace-change template
    - .deploy-template  # Common deployment configuration and scripts
    - .deploy-k8s-namespace  # Specific steps to deploy the Kubernetes namespace
    - .dev-change  # Conditions for running this job (specific to 'dev' environment)

# Job for deploying to the 'prod' environment
prod-deploy-{NAMESPACE}:
  extends:
    - .{NAMESPACE}-namespace-change
    - .deploy-template
    - .deploy-k8s-namespace
    - .prod-change  # Conditions for running this job (specific to 'prod' environment)

# Job for deploying to the 'devdmz' environment
devdmz-deploy-{NAMESPACE}:
  extends:
    - .{NAMESPACE}-namespace-change
    - .deploy-template
    - .deploy-k8s-namespace
    - .devdmz-change  # Conditions for running this job (specific to 'devdmz' environment)

# Job for deploying to the 'proddmz' environment
proddmz-deploy-{NAMESPACE}:
  extends:
    - .{NAMESPACE}-namespace-change
    - .deploy-template
    - .deploy-k8s-namespace
    - .proddmz-change  # Conditions for running this job (specific to 'proddmz' environment)

# Job for deploying to the 'procdmz' environment
procdmz-deploy-{NAMESPACE}:
  extends:
    - .{NAMESPACE}-namespace-change
    - .deploy-template
    - .deploy-k8s-namespace
    - .procdmz-change  # Conditions for running this job (specific to 'procdmz' environment)

"""
        return child_pipeline_job_template

    @staticmethod
    def child_pipeline_job_template_project(PROJECT):
        child_pipeline_job_template = f"""

# Job template for changes in the Argo CD project configuration
.{PROJECT}-argocd-proj-change:
  variables:
    PROJECT: "{PROJECT}"  # Sets the PROJECT variable for use in the job
  only:
    changes:
      - "manifests/argocd-proj-workflow/{PROJECT}**"  # Runs only if there are changes in the specified project setup files
  when: always  # This job will always run, regardless of the status of previous stages or jobs

# Job for deploying the Argo CD project to the 'dev' environment
dev-deploy-{PROJECT}:
  extends:
    - .{PROJECT}-argocd-proj-change  # Extends the .{PROJECT}-argocd-proj-change template
    - .deploy-template  # Common deployment configuration and scripts
    - .deploy-argo-app-project  # Specific steps to deploy the Argo CD project
    - .dev-change  # Conditions for running this job (specific to 'dev' environment)

# Job for deploying the Argo CD project to the 'devdmz' environment
devdmz-deploy-{PROJECT}:
  extends:
    - .{PROJECT}-argocd-proj-change
    - .deploy-template
    - .deploy-argo-app-project
    - .devdmz-change  # Conditions for running this job (specific to 'devdmz' environment)

# Job for deploying the Argo CD project to the 'prod' environment
prod-deploy-{PROJECT}:
  extends:
    - .{PROJECT}-argocd-proj-change
    - .deploy-template
    - .deploy-argo-app-project
    - .prod-change  # Conditions for running this job (specific to 'prod' environment)

# Job for deploying the Argo CD project to the 'proddmz' environment
proddmz-deploy-{PROJECT}:
  extends:
    - .{PROJECT}-argocd-proj-change
    - .deploy-template
    - .deploy-argo-app-project
    - .proddmz-change  # Conditions for running this job (specific to 'proddmz' environment)

# Job for deploying the Argo CD project to the 'procdmz' environment
procdmz-deploy-{PROJECT}:
  extends:
    - .{PROJECT}-argocd-proj-change
    - .deploy-template
    - .deploy-argo-app-project
    - .procdmz-change  # Conditions for running this job (specific to 'procdmz' environment)

"""
        return child_pipeline_job_template

    @staticmethod
    def child_pipeline_job_template_application(PROJECT, APPLICATION):
        child_pipeline_job_template = f"""

# Job template for changes in the Argo CD application configuration
.{APPLICATION}-{PROJECT}-argocd-app-change:
  variables:
    PROJECT: "{PROJECT}"
    APPLICATION: "{APPLICATION}"
  only:
    changes:
      - "manifests/argocd-app-workflow/{PROJECT}/{APPLICATION}**"
  when: always  # This job will always run, regardless of the status of previous stages or jobs

# Jobs for deploying the Argo CD application to various environments

dev-deploy-{APPLICATION}-{PROJECT}:
  extends:
    - .{APPLICATION}-{PROJECT}-argocd-app-change
    - .deploy-template  # Common deployment configuration and scripts
    - .deploy-argo-application  # Specific steps to deploy the Argo CD application
    - .dev-change  # Conditions for running this job (specific to 'dev' environment)

devdmz-deploy-{APPLICATION}-{PROJECT}:
  extends:
    - .{APPLICATION}-{PROJECT}-argocd-app-change
    - .deploy-template
    - .deploy-argo-application
    - .devdmz-change  # Conditions for running this job (specific to 'devdmz' environment)

prod-deploy-{APPLICATION}-{PROJECT}:
  extends:
    - .{APPLICATION}-{PROJECT}-argocd-app-change
    - .deploy-template
    - .deploy-argo-application
    - .prod-change  # Conditions for running this job (specific to 'prod' environment)

proddmz-deploy-{APPLICATION}-{PROJECT}:
  extends:
    - .{APPLICATION}-{PROJECT}-argocd-app-change
    - .deploy-template
    - .deploy-argo-application
    - .proddmz-change  # Conditions for running this job (specific to 'proddmz' environment)

procdmz-deploy-{APPLICATION}-{PROJECT}:
  extends:
    - .{APPLICATION}-{PROJECT}-argocd-app-change
    - .deploy-template
    - .deploy-argo-application
    - .procdmz-change  # Conditions for running this job (specific to 'procdmz' environment)

# Job for adding a repository to Argo CD in the 'dev' environment
dev-argocd-add-repository-{APPLICATION}-{PROJECT}:
  variables:
    URL: $CI_DEV_ARGOCD_SERVER  # Argo CD server URL for the 'dev' environment
    USERNAME: $CI_DEV_ARGOCD_USERNAME  # Argo CD username for the 'dev' environment
    PASSWORD: $CI_DEV_ARGOCD_PASSWORD  # Argo CD password for the 'dev' environment
  extends: 
    - .{APPLICATION}-{PROJECT}-argocd-app-change  # Base job template for the application and project
    - .argocd-add-repository  # Shared configuration for adding a repository
    - .dev-change  # Specifies the conditions under which this job runs (for 'dev' branch)
  resource_group: development  # Specifies the resource group for this job

devdmz-argocd-add-repository-{APPLICATION}-{PROJECT}:
  # Variables and extends similar to the 'dev' environment job, tailored for the 'devdmz' environment
  variables:
    URL: $CI_DEVDMZ_ARGOCD_SERVER
    USERNAME: $CI_DEVDMZ_ARGOCD_USERNAME
    PASSWORD: $CI_DEVDMZ_ARGOCD_PASSWORD
  extends: 
    - .{APPLICATION}-{PROJECT}-argocd-app-change
    - .argocd-add-repository
    - .devdmz-change
  resource_group: development

prod-argocd-add-repository-{APPLICATION}-{PROJECT}:
  # Variables and extends similar to the 'dev' environment job, tailored for the 'prod' environment
  variables:
    URL: $CI_PROD_ARGOCD_SERVER
    USERNAME: $CI_PROD_ARGOCD_USERNAME
    PASSWORD: $CI_PROD_ARGOCD_PASSWORD
  extends: 
    - .{APPLICATION}-{PROJECT}-argocd-app-change
    - .argocd-add-repository
    - .prod-change
  resource_group: production

proddmz-argocd-add-repository-{APPLICATION}-{PROJECT}:
  # Variables and extends similar to the 'dev' environment job, tailored for the 'proddmz' environment
  variables:
    URL: $CI_PRODDMZ_ARGOCD_SERVER
    USERNAME: $CI_PRODDMZ_ARGOCD_USERNAME
    PASSWORD: $CI_PRODDMZ_ARGOCD_PASSWORD
  extends: 
    - .{APPLICATION}-{PROJECT}-argocd-app-change
    - .argocd-add-repository
    - .proddmz-change
  resource_group: production

procdmz-argocd-add-repository-{APPLICATION}-{PROJECT}:
  # Variables and extends similar to the 'dev' environment job, tailored for the 'procdmz' environment
  variables:
    URL: $CI_PROCDMZ_ARGOCD_SERVER
    USERNAME: $CI_PROCDMZ_ARGOCD_USERNAME
    PASSWORD: $CI_PROCDMZ_ARGOCD_PASSWORD
  extends: 
    - .{APPLICATION}-{PROJECT}-argocd-app-change
    - .argocd-add-repository
    - .procdmz-change
  resource_group: production

"""
        return child_pipeline_job_template

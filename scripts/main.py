from git import Repo
import os
from template import PipelineWriter

pipelineFilename = "child-pipeline-gitlab-ci.yml"

# Directories
namespace_directory = "manifests/k8s-namespace-setup"
argo_app_project_directory = "manifests/argocd-proj-workflow"
argo_application_directory = "manifests/argocd-app-workflow"

def get_files_from_last_commit(repo_path):
    """
    Returns a list of file names that were changed in the last commit of the given repository.
    """
    repo = Repo(repo_path)
    last_commit = next(repo.iter_commits())

    # Check if there is a parent commit to compare against
    if last_commit.parents:
        diff = last_commit.diff(last_commit.parents[0])
    else:
        # If it's the very first commit, compare against an empty tree
        diff = last_commit.diff(None)

    changed_files = [item.a_path for item in diff]
    return changed_files

def parse_file_name(file_path):
    """
    Parses the file path to extract relevant parts based on directory structure.
    """
    parts = file_path.split('/')

    # Handle cases where the file is in the root directory (e.g., '.gitlab-ci.yml')
    if len(parts) == 1:
        return file_path.replace('.yml', '')  # or return an appropriate value

    # Extract the main directory (e.g., 'argocd_app_workflow')
    directory = parts[1]  

    if directory == namespace_directory.split('/')[1]:
        return parts[-1].replace('.yml', '')

    elif directory == argo_app_project_directory.split('/')[1]:
        return parts[-1].replace('.yml', '')

    elif directory == argo_application_directory.split('/')[1]:
        if len(parts) > 2:
            folder_name = parts[2]
            file_name = parts[-1].replace('.yml', '')
            return folder_name, file_name
        return directory  # or handle this case as needed

    return file_path.replace('.yml', '')

def generator():
    repo_path = '.'

    # Get the list of changed files in the last commit
    changed_files = get_files_from_last_commit(repo_path)

    with open(pipelineFilename, 'w') as file:
        file.write(PipelineWriter.parent_job_template())

        for file_name in changed_files:
            # Extract directory and file parts
            file_parts = parse_file_name(file_name)

            if file_name.startswith(namespace_directory):
                # Process namespace files
                namespace = file_parts
                file.write(PipelineWriter.child_pipeline_job_template_namespace(namespace))

            elif file_name.startswith(argo_app_project_directory):
                # Process project files
                project = file_parts
                file.write(PipelineWriter.child_pipeline_job_template_project(project))

            elif file_name.startswith(argo_application_directory):
                # Process application files
                folder_name, application = file_parts
                file.write(PipelineWriter.child_pipeline_job_template_application(folder_name, application))
            

if __name__ == "__main__":
    generator()

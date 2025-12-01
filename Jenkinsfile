pipeline {
    agent any

    environment {
        COMPOSE_FILE = 'docker-compose.yml'
        SONAR_HOME   = tool 'sonar'
        GIT_URL      = "https://github.com/Snayak97/jenkins_ism.git"
        GIT_BRANCH   = "main"
        VERSION      = "v1.0.0"
        APP_NAME     = "Ism_project"
    }

    options {
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '10'))
        disableConcurrentBuilds()
        skipDefaultCheckout(true)
        ansiColor('xterm')
    }

    stages {

        stage('Cleanup') {
            steps {
                script {
                    echo "========== CLEANUP START =========="

                    try {
                        deleteDir()
                        echo "Workspace cleaned"

                        sh '''
                          which docker || { echo "Docker not installed"; exit 1; }
                          docker compose down -v || echo "No running containers"
                        '''
                    } catch (err) {
                        echo "Cleanup failed: ${err}"
                        error("Stopping pipeline — cleanup stage failed.")
                    }

                    echo "========== CLEANUP END =========="
                }
            }
        }

        stage('Checkout Code') {
            steps {
                script {
                    echo "========== CHECKOUT START =========="

                    retry(3) {
                        try {
                            checkout([
                                $class: 'GitSCM',
                                branches: [[name: "*/${GIT_BRANCH}"]],
                                userRemoteConfigs: [[url: "${GIT_URL}"]]
                            ])
                            echo "Checkout successful"
                        } catch (err) {
                            echo "Git checkout failed: ${err}"
                            echo "Retrying in 3 seconds..."
                            sleep 3
                            throw err
                        }
                    }

                    echo "========== CHECKOUT END =========="
                }
            }
        }

        stage('Debug Workspace') {
            steps {
                script {
                    echo "========== WORKSPACE DEBUG START =========="

                    try {
                        sh '''
                          echo "---- Directory ----"
                          pwd

                          echo "---- Files ----"
                          ls -la

                          echo "---- Checking Required Files ----"
                          test -f docker-compose.yml        || { echo "docker-compose.yml missing"; exit 1; }
                          test -f Backend/run.py            || { echo "Backend run.py missing"; exit 1; }
                          test -f fontend/package.json      || { echo "Frontend package.json missing"; exit 1; }

                          echo "---- Git Status ----"
                          git status || echo "Not a git repo"
                        '''
                        echo "Workspace validation passed"
                    } catch (err) {
                        echo "Workspace validation failed: ${err}"
                        error("Stopping pipeline — required files missing.")
                    }

                    echo "========== WORKSPACE DEBUG END =========="
                }
            }
        }
        stage('OWASP Dependency Check') {
            steps {
                dependencyCheck additionalArguments: '--scan ./', odcInstallation: 'dc'
                dependencyCheckPublisher pattern: "**/dependency-check-report.html"
                
            }
        }

        stage('SonarQube Analysis') {
            steps {
                echo "Starting SonarQube Analysis..."
                script {
                    retry(2) {
                        withSonarQubeEnv("sonar") {
                            try {
                                sh """
                                    ${SONAR_HOME}/bin/sonar-scanner \
                                    -Dsonar.projectKey=${APP_NAME} \
                                    -Dsonar.projectName=${APP_NAME} \
                                    -Dsonar.sources=. 
                                """
                                echo "SonarQube analysis completed successfully."
                            } catch (Exception err) {
                                echo "SonarQube analysis failed: ${err}"
                                error "SonarQube stage failed"
                            }
                        }
                    }
                }
            }
        }

        stage('Quality Gate Check') {
            steps {
                timeout(time: 3, unit: 'MINUTES') {
                    script {
                        try {
                            def qg = waitForQualityGate(abortPipeline: false)

                            echo "Quality Gate Status: ${qg.status}"

                            if (qg.status != 'OK') {
                                echo "Quality Gate FAILED — Status: ${qg.status}"
                                error "Pipeline stopped because Quality Gate failed: ${qg.status}"
                            }

                            echo "Quality Gate PASSED successfully."

                        } catch (Exception err) {
                            echo "Error while checking Quality Gate: ${err}"
                            error "Quality Gate Check failed unexpectedly."
                        }
                    }
                }
            }
        }

        stage('Docker Build') {
            steps {
                script {
                    echo "========== DOCKER BUILD START =========="

                    try {
                        def IMAGE_NAME_BACKEND  = "ism_project-backend"
                        def IMAGE_NAME_FRONTEND = "ism_project-frontend"

                        sh """
                            which docker >/dev/null 2>&1 || { echo 'Docker not installed'; exit 1; }
                            docker compose version >/dev/null 2>&1 || { echo 'Docker Compose not installed'; exit 1; }
                            test -f ${COMPOSE_FILE} || { echo 'Missing compose file'; exit 1; }

                            echo 'Building Docker images...'
                            docker compose -f ${COMPOSE_FILE} build --no-cache
                            
                            docker tag ism_project-backend:latest ism_project-backend:${VERSION}
                            docker tag ism_project-frontend:latest ism_project-frontend:${VERSION}

                            echo 'Cleaning dangling images...'
                            docker image prune -f
                        """

                        echo "Docker build completed."

                    } catch (err) {
                        echo "Docker build failed: ${err}"
                        error("Stopping pipeline — Docker Build stage failed.")
                    }

                    echo "========== DOCKER BUILD END =========="
                }
            }
        }

        stage('DockerHub Login & Push') {
            steps {
                script {
                    echo "========== DOCKERHUB LOGIN & PUSH START =========="

                    try {
                        def IMAGE_BACKEND  = "ism_project-backend"
                        def IMAGE_FRONTEND = "ism_project-frontend"

                        def DOCKER_REPO_BACKEND  = "snayak97/ism_project-backend"
                        def DOCKER_REPO_FRONTEND = "snayak97/ism_project-frontend"

                        withCredentials([usernamePassword(
                            credentialsId: 'dockerhub-creds',
                            usernameVariable: 'DOCKER_USER',
                            passwordVariable: 'DOCKER_PASS'
                        )]) {

                            sh """
                                echo 'Logging in to DockerHub...'
                                echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin

                                echo 'Tagging & pushing backend image...'
                                docker tag ${IMAGE_BACKEND}:latest ${DOCKER_REPO_BACKEND}:${VERSION}
                                docker tag ${IMAGE_BACKEND}:latest ${DOCKER_REPO_BACKEND}:latest 
                                docker push ${DOCKER_REPO_BACKEND}:${VERSION}
                                docker push ${DOCKER_REPO_BACKEND}:latest

                                echo 'Tagging & pushing frontend image...'
                                docker tag ${IMAGE_FRONTEND}:latest ${DOCKER_REPO_FRONTEND}:${VERSION}
                                docker tag ${IMAGE_FRONTEND}:latest ${DOCKER_REPO_FRONTEND}:latest
                                docker push ${DOCKER_REPO_FRONTEND}:${VERSION}
                                docker push ${DOCKER_REPO_FRONTEND}:latest

                                docker logout
                            """
                        }

                        echo "DockerHub push completed successfully."

                    } catch (err) {
                        echo "DockerHub push failed: ${err}"
                        error("Stopping pipeline — DockerHub Push stage failed.")
                    }

                    echo "========== DOCKERHUB LOGIN & PUSH END =========="
                }
            }
        }

        stage('Deploy code') {
            steps {
                script {
                    echo "========== DEPLOY START =========="

                    try {
                        sh """
                            echo 'Pulling backend and frontend images...'
                            docker pull snayak97/ism_project-backend:${VERSION}
                            docker pull snayak97/ism_project-frontend:${VERSION}

                            echo 'Deploying using Docker Compose...'
                            docker compose -f ${COMPOSE_FILE} up -d --remove-orphans
                        """

                        echo "Deployment completed successfully."
                    } catch (err) {
                        echo "Deployment failed: ${err}"
                        error("Stopping pipeline — Deployment stage failed.")
                    }

                    echo "========== DEPLOY END =========="
                }
            }
        }

    } // END of stages

    post {
        always {
            echo "Pipeline completed (success/failure)."
        }
        success {
            echo "Pipeline succeeded"
        }
        failure {
            echo "Pipeline failed"
        }
        cleanup {
            echo "Final cleanup (always runs)"
        }
    }
}

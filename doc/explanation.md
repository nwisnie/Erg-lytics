# Explanation Erg-lytics

## System Overview

Erg-lytics is a web based application that will help rowers to improve their rowing technique on the erg.

Our system is split into a browser-based frontend, a Flask application running in AWS Lambda, and a small set of AWS services that handle auth, storage, and media.

Our system has functionality that analyzes a rower’s technique in real time using live video input and provides targeted feedback through immediate audio cues and post-workout video snippets with detailed explanations. Our system also stores results based on the aforementioned analysis, and those results can be viewed by other rowers and coaches on their team.

Our current system is built around a serverless model:
- API Gateway handles incoming requests
- Lambda runs the Flask app
- Cognito handles authentication
- DynamoDB stores user/team/workout data
- S3 stores uploaded recordings.

Such a setup keeps the architecture lightweight while still covering the core product needs.

## Architecture Diagrams

This section builds on these diagrams in the repo:
- `doc/rowlytics_trust_boundary.drawio`
- `doc/rowlytics_attack_tree.drawio`

At a high level, the architecture looks like this:
1. A user interacts with the Erg-lytics frontend in the browser.
2. The frontend talks to the Flask app through API Gateway.
3. The Flask app uses Cognito for login, DynamoDB for application data, and S3 for uploaded media.
4. CV and feature-extraction logic runs inside the app layer to turn recorded movement into feedback data.

The system can also be thought of as these three segments:
- **Client layer:** browser UI and JavaScript code
- **App layer:** Flask routes, auth/session handling, API endpoints, and CV logic
- **AWS layer:** Cognito, DynamoDB, S3, and CloudWatch

## Key Components

### Frontend
Our frontend is mostly HTML templates with CSS and page-specific JavaScript. This setup keeps our app small and easier manage compared using to a traditional frontend framework like React, but it is harder to add interactivity to our frontend as a result.

### Flask Application
We use Flask is our core app layer because it handles page rendering, API routes, session logic, and links our UI to our AWS services. To make such an approach work, we use a mix of traditional page navigation and API-driven features, and Flask is flexible enough to support both without much overhead.

### Authentication
We use Cognito so we don't need to build account creation, password handling, or token flows from the ground up. The tradeoff with Cognito though is that its user flow is unlfexible, especially around signup and account confirmation, but that's a pretty small price to pay for good security.

### Data Storage
We use DynamoDB to store users, teams, memberships, recordings, and workouts. We use DynamoDB specifically because our access patterns are pretty direct and key-based. The main downside with DynamoDB though is that schema changes are not as casual as they would be in a relational database.

### Media Storage and Analysis
We use S3 to store uploaded workout videos, and our app handles the actual analysis. Based on live video being captured, our CV algorithm focuses on body points, posture, and joint angles to make form judgements. That makes the system easier to understand, troubleshoot, and explain to both users and reviewers..

## Design Decisions

### Why Flask / Lambda
We use Flask and Lambda because it gives a pretty good mix between speed of development and deployment simplicity. We like Flask because several team members are familiar with it, is easy to write tests (with Pytest), and is relatively easy to extend. We like Lambda and API Gateway because they reduce the amount of infrastructure we need to manage, which is great for saving time and money.

### Why Server-Rendered Pages
We use mostly server rendered pages because they keep our app lighter than a large single-page frontend. Also, we feel that we don't need a large frontend framework to handle our current workflows.

### Why AWS Managed Services
We use Cognito, DynamoDB, S3, and CloudWatch so that our the team focus more on product behavior and CV logic and not get lost in the minutiae of account security, database administration, and file infrastructure.

## Tradeoffs and Limitations
Overall, our current design works, but it has some tradeoffs:
- Our hosted Cognito experience is convenient, but not very customizable.
- DynamoDB scales well, but it pushes the team toward access-pattern-driven design.
- Lambda keeps ops light, but debugging deployed path and environment issues can be difficult.
- Our CV pipeline is explainable, but it may not capture every edge case in a real rowing motion or camera setup.

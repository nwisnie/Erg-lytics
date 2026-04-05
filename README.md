# Rowlytics

Rowlytics is a web based application that will help rowers to improve their rowing technique on the erg.<br><br>
Our primary objective is to build a web-based application that analyzes a rower’s technique in real time using live video input and provides targeted feedback through immediate audio cues and post-workout video snippets with detailed explanations. Additionally, our project aims to assist coaches by providing a team management interface that displays detailed technique analysis data for each rower on a team, including recorded instances of poor form and statistics on the frequency and types of technique errors.

## How Will We Judge Technique?
As a user rows, each stroke will be rated based on how far the user deviates from our ideal model. The ratings will not be based on the user’s stroke timing, but rather how closely the user’s body is positioned relative to the ideal model at three key positions: stroke start, mid stroke, and stroke completion. <br><br>
![Parts of Rowing Stroke](https://github.com/nwisnie/Erg-lytics/blob/main/rowlytics_app/static/images/super_stroker.png) <br><br>
Right now, our plan is to have a score from 0 to 1 for the user’s hand/arm position *(should be straight during mid stroke for example)*, back position *(no slouching during the stroke start for example)*, and leg position *(should be straight during stroke completion for example)*. We plan to calculate each of these scores during all three portions of the stroke. When the rower finishes a workout, all of these scores will be tallied and the user will be able to see their total score, their average score for each portion of the stroke, and their average score for each body part.

## CV Limitations, Assumptions and Ethical Notes
Erglytics currently evaluates rowing posture using a side-view camera setup and compares detected body landmarks to an idealized stroke model. Because of this, even if the system says that your position is correct, results may be less reliable when:

- the user is not fully visible from one side
- the camera angle is not close to a side profile
- lighting is poor or parts of the body are occluded
- loose clothing, background clutter, or low video quality make landmarks hard to detect
- the user’s body proportions, mobility, adaptive technique, or rowing style differ STRONGLY from the assumptions in the current model

The scores should be treated as coaching assistance, not a medical diagnosis or safety advice. A lower score does not indicate immediately that the user is rowing incorrectly; it may reflect camera placement, visibility issues, or model limitations.

## Team-Centric Design
Users are encouraged to take advantage of our team system by joining team! <br><br>
Users on a team can either have the rower our coach status: <br>
- **Coaches** - can moderate the team by adding or removing rowers
- **Rowers** - can view and compare stats with other rowers on the team

*The creator of a team will be given the coach status. A coach can then give a rower the coach status.*

## Contributors
- Noah Wisniewski
- Kassie Bankson
- Aidan Mahaffey :)
- Evan Osborne

## Getting started
1. Make sure Python and `pip` are installed.
2. (Optional) Create and activate a virtual environment.
3. Install dependencies and register pre-commit hooks:
   ```bash
   make dev-install
   ```
4. Run the development server with hot reload:
   ```bash
   ./scripts/dev_server.sh
   ```

## Backend Deployment (AWS SAM)

Rowlytics uses **AWS SAM** to deploy the backend infrastructure (Lambda, API Gateyway, DynamoDB, and S3).

From the 'backend/' directory:

 ```bash
sam build
sam deploy
```

The deployment configuration is stored in 'samconfig.toml'.

Do *not deploy with ManageSharedResources as true*, unless you intend to create/rewrite the resources. It should be *false* on default.

Be sure to *change the stack name to the correct stack* for your task (erglytics-dev, erglytics-version-..., erglytics-ui-test, etc.) to not overwrite incorrect stacks.

### Connecting Cognito Page to New Stack

When creating a new stack, ensure that after initial deployment, and updating the base api url, that url is added to the *Cognito Allowed Sign Out URLs and Allowed Callback URLs*. This is found in Cognito Console, by selecting the UserPool, going to App clients, selecting the app client, and navigating to the *Login pages* section. Just follow the same format and add the new base url to both sections by editing.

### Important: Table Names

The dev stack uses the **Recovery DynamoDB tables and bucket**. These resources already exist in AWS and must be used when deploying.

| Parameter | Resource |
|-----------|----------|
| UsersTableName | RowlyticsUsersRecovery |
| TeamsTableName | RowlyticsTeamsRecovery |
| TeamMembersTableName | RowlyticsTeamMembersRecovery |
| RecordingsTableName | RowlyticsRecordingsRecovery |
| WorkoutsTableName | RowlyticsWorkoutsRecovery |
| UploadBucketName | rowlyticsupload-recovery-793523315638 |

These values *should* already be configred in 'samconfig.toml'.

## Quality gates
- `make lint` runs flake8 and isort.
- `make test` runs pytest.
- `make check` runs both lint + tests.
- `.pre-commit-config.yaml` mirrors the CI checks locally. Enable it with `pre-commit install` (already done via `make dev-install`).

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and pull request to `main`. A push will fail unless all quality gates are passed.

## Version
Version Number: 0.5.1

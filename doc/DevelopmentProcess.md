# Development Process

## Repository Architecture

Erglytics/<br>
├─ backend/<br>
├─ rowlytics_app/<br>
│  ├─ routes/<br>
│  ├─ auth/<br>
│  ├─ services/<br>
│  ├─ templates/<br>
│  └─ static/<br>
├─ cv/<br>
│  ├─ detectors/<br>
│  ├─ tracking/<br>
│  ├─ feature_extraction/<br>
│  └─ models/<br>
├─ scripts/<br>
├─ tests/<br>
└─ docs/<br>

**Descriptions:**
- **backend/** houses our SAM template and deploy config
- **rowlytics_app/** contains our Flask app package
- **cv/** will contain our CV pipeline (future)
- **scripts/** is used for setup and other specific actions
- **tests/** has unit and integration tests
- **docs/** contains our documentation

**References:**
- Flask Structuring: https://flask.palletsprojects.com/en/3.0.x/blueprints/
- Python Project Layout: https://packaging.python.org/en/latest/tutorials/packaging-projects/
- AWS SAM: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-template-basics.html

## Branching
Our repository branching architecture will utilize a simple one branch downstream of the main approach. That is, every branch present in our repository will be a direct off-shoot of the main branch. This is in order to reduce the number of merge conflicts by reducing the number of nodes present in our repository. We are also structuring our branching architecture this way in order to reduce feature creep, so we won’t be tempted to make sub-branches to integrate other features that may not be necessary for the initial scope of a feature.

Our branch naming convention is simple: lowercase letters, underscores, and numbers are used to describe the particular feature under development in that branch.

Ex:
main_feedback_loop
model_extraction_class

In these branches, only the described features will be worked on. Once finished, the branch will be merged into main after it passes the required CI tests.

The exception to the standard branch flow are personal branches. Each member of the group has a personal branch that will be a space for independent development or experimentation. Members may create sub-branches from their own personal branches as they desire, however no critical project work should be completed in the personal branch and should instead be completed in a conventional branch as highlighted above.


## Code Developement and Review Policy
Several Rules will be established for merging into the main branch. Firstly We will use Flake8 formating which requires that all files follow a formatting guide specified
in the .flake8 file. Secondly, the merged code must pass all unit tests specificed in the /tests directory. These merges will be done with merges between feature branches
and the main branch. We will primarily do these during code reviews which occur during the end of sprints. We have 9 sprints, so we will push to main 9 times.
Pushing to a feature branch will have the rule of being non-destructive of the work of other teammates. We have our own branches for the purposes of doing modifying work.

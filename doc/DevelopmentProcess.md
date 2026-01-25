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

## Code Developement and Review Policy
Several Rules will be established for merging into the main branch. Firstly We will use Flake8 formating which requires that all files follow a formatting guide specified
in the .flake8 file. Secondly, the merged code must pass all unit tests specificed in the /tests directory. These merges will be done with merges between feature branches
and the main branch. We will primarily do these during code reviews which occur during the end of sprints. We have 9 sprints, so we will push to main 9 times.
Pushing to a feature branch will have the rule of being non-destructive of the work of other teammates. We have our own branches for the purposes of doing modifying work.

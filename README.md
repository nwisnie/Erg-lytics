# Rowlytics

Rowlytics is a web based application that will help rowers to improve their rowing technique on the erg.<br><br>
Our primary objective is to build a web-based application that analyzes a rower’s technique in real time using live video input and provides targeted feedback through immediate audio cues and post-workout video snippets with detailed explanations. Additionally, our project aims to assist coaches by providing a team management interface that displays detailed technique analysis data for each rower on a team, including recorded instances of poor form and statistics on the frequency and types of technique errors.

## How Will We Judge Technique?
As a user rows, each stroke will be rated based on how far the user deviates from our ideal model. The ratings will not be based on the user’s stroke timing, but rather how closely the user’s body is positioned relative to the ideal model at three key positions: stroke start, mid stroke, and stroke completion. <br><br>
![Parts of Rowing Stroke](https://github.com/nwisnie/Erg-lytics/blob/main/rowlytics_app/static/images/super_stroker.png) <br><br>
Right now, our plan is to have a score from 0 to 1 for the user’s hand/arm position *(should be straight during mid stroke for example)*, back position *(no slouching during the stroke start for example)*, and leg position *(should be straight during stroke completion for example)*. We plan to calculate each of these scores during all three portions of the stroke. When the rower finishes a workout, all of these scores will be tallied and the user will be able to see their total score, their average score for each portion of the stroke, and their average score for each body part.

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

## Quality gates
- `make lint` runs flake8 and isort.
- `make test` runs pytest.
- `make check` runs both lint + tests.
- `.pre-commit-config.yaml` mirrors the CI checks locally. Enable it with `pre-commit install` (already done via `make dev-install`).

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and pull request to `main`. A push will fail unless all quality gates are passed.

## Version
Version Number: 0.5.1

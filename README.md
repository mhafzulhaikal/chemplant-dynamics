# ChemPlant Dynamics

## Executive Summary

ChemPlant Dynamics is a computational framework for modeling, simulating, and analyzing dynamic chemical process systems with emphasis on reactor and thermal process behavior. The project integrates process engineering fundamentals, control-system modeling, and interactive visualization to support academic study, engineering analysis, and prototype evaluation of industrial process control strategies.

The repository is designed around a modular architecture that separates process models, controller logic, system configuration, and application interfaces. It supports multiple case studies, including biodiesel reactor dynamics and a stirred tank heat reactor (STHR) system, enabling investigation of transient behavior, process control performance, and simulation-based design decisions.

## 1. Introduction

### 1.1 Background

Chemical plants are complex, nonlinear, dynamic systems that require careful monitoring and control to ensure safe, efficient, and stable operation. Process variables such as temperature, level, concentration, and flow are strongly coupled and often exhibit delayed or nonlinear responses. These characteristics make dynamic simulation and control analysis essential in process engineering education and research.

ChemPlant Dynamics addresses this need by providing a reusable simulation environment for chemical process systems. The platform combines:

- dynamic plant models
- actuator and sensor systems
- controller design and tuning
- system configuration and case studies
- a web-based user interface for visualization and analysis

### 1.2 Research and Educational Relevance

This project is relevant to multiple domains, including:

- process control education
- chemical process modeling and simulation
- control-system design validation
- transient response analysis
- digital process monitoring and industrial prototyping

The repository is particularly suitable for academic coursework, thesis work, research prototyping, and engineering demonstrations involving dynamic process systems.

## 2. Project Objectives

The primary objectives of this project are to:

1. develop a software framework for dynamic chemical process simulation;
2. represent key process units using model-based formulations;
3. evaluate system behavior under open-loop and closed-loop conditions;
4. provide controller structures for interactive tuning and analysis;
5. support visualization of process variables and system responses;
6. facilitate educational and research exploration of plant dynamics.

## 3. System Scope

The repository includes models for chemical process systems and control structures that reflect realistic dynamic behavior. The current implementation includes:

- Biodiesel reactor model
- Stirred tank heat reactor model (STHR)
- Actuator system models
- Sensor/transmitter models
- Setpoint and controller systems
- Interactive application layer for visualization and control testing

## 4. Repository Structure

```text
chemplant-dynamics/
├── app/                         # Interactive application and UI layer
│   ├── api/                    # API endpoints and health routes
│   ├── components/             # Reusable UI components
│   ├── hub/                    # Centralized app hub logic
│   ├── layouts/                # Page layouts and wrappers
│   ├── pages/                  # Page implementations
│   ├── pid/                    # PID-related UI logic
│   ├── static/                 # Static frontend assets
│   ├── ui/                     # UI modules and widgets
│   ├── assets.py               # App asset definitions
│   ├── config.py               # App configuration
│   ├── main.py                 # Development entrypoint
│   ├── nicegui_patch.py        # NiceGUI compatibility patch
│   ├── server.py               # App server / production entrypoint
│   ├── biodiesel_drawing.py    # Biodiesel process drawing utilities
│   └── sthr_drawing.py         # STHR drawing utilities
│
├── cases/                      # Case studies and scenario definitions
│   ├── biodiesel/
│   ├── common/
│   └── sthr/
│
├── docs/                       # Project documentation and notes
│
├── engine/                     # Simulation engine / orchestration utilities
│
├── gateway/                    # Gateway / integration layer
│
├── models/                     # Dynamic process models and system blocks
│   ├── actuator.py
│   ├── base.py
│   ├── controller.py
│   ├── plant.py
│   ├── sensor.py
│   ├── setpoint.py
│   └── __init__.py
│
├── systems/                    # System configuration and builder modules
│   ├── builders/
│   └── configs/
│
├── .dockerignore
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── .python-version
├── Dockerfile
├── DOCKER.md
├── docker-compose.yml
├── pyproject.toml
├── uv.lock
├── README.md
└── LICENSE                     # if added in the project
```

## 5. Core Components

### 5.1 Model Layer (`models/`)

The `models/` package contains the mathematical representations of the primary process and control elements.

- `plant.py`: contains the dynamic process models, including:
  - Biodiesel reactor system
  - STHR system
  - state-space and nonlinear dynamic formulations
- `actuator.py`: actuator dynamics and valve-control behavior
- `sensor.py`: sensor/transmitter models and measurement dynamics
- `controller.py`: controller implementations, including feedback/control logic
- `setpoint.py`: setpoint generation and control tracking support
- `base.py`: common base definitions for process system objects

These model classes support simulation workflows and provide structure for controller tuning and performance evaluation.

### 5.2 Application Layer (`app/`)

The application layer provides a browser-based interface for interacting with the dynamic models. It uses a modern Python UI framework and exposes process visualizations and control interactions.

Key responsibilities include:

- process visualization
- system configuration
- interactive control panels
- plant schematic rendering
- simulation-monitoring interfaces

The app layer is organized to separate visual rendering, configuration, and web endpoints for deployment and local experimentation.

### 5.3 Case Studies (`cases/`)

The repository contains structured case definitions for specific process scenarios. The included directories suggest a modular design where case-specific parameter sets and benchmarking scenarios can be developed and managed independently.

This supports use in:

- comparative system studies
- scenario analysis
- process performance benchmarking
- evaluation of controller response under different operating conditions

### 5.4 System Configurations (`systems/`)

The `systems/` directory is designed to store reusable system builders and configuration definitions for assembling plant models, controllers, and simulation structures in a consistent way.

## 6. Mathematical and Engineering Context

### 6.1 Dynamic Process Modeling

The project models dynamic chemical processes using nonlinear differential equations, which capture the interaction between state variables and manipulated inputs. This approach is well-suited for investigating how process variables evolve over time under changing operating conditions.

In the plant model, system states may include:

- reactor level or holdup
- component concentrations
- reactor temperature
- coolant temperature
- material flow conditions

The equations reflect the mass and energy balances required for realistic reactor and thermal system behavior.

### 6.2 Control System Perspective

Control is a central element of the project. The control layer includes:

- actuator response modeling
- setpoint definition
- feedback control implementation
- monitoring and tuning interfaces

This is important because process performance depends not only on plant dynamics but also on controller behavior under disturbances, setpoint changes, and process constraints.

### 6.3 Simulation Workflow

The repository supports a typical engineering workflow:

1. define or select a process case,
2. instantiate the model and controller,
3. run dynamic simulation,
4. observe responses in the interface or data output,
5. tune parameters and evaluate performance.

This workflow mirrors standard process-control and systems-engineering practice.

## 7. Technology Stack

### Python Stack

The project is implemented primarily in Python using scientific and process-engineering libraries, including:

- `numpy`
- `scipy`
- `control`
- `fastapi`
- `nicegui`
- `uvicorn`
- `drawsvg`

### Development Tools

- `ruff` for linting and formatting
- `pyright` for static type checking
- `pre-commit` for code quality control
- Docker / Docker Compose for packaging and deployment

## 8. Installation and Setup

### 8.1 Prerequisites

- Python 3.14+
- `uv` or `pip`
- Docker (optional, for containerized deployment)

### 8.2 Install Dependencies

Using `uv`:

```bash
git clone https://github.com/mhafzulhaikal/chemplant-dynamics.git
cd chemplant-dynamics
uv sync --group dev
```

Using `pip`:

```bash
git clone https://github.com/mhafzulhaikal/chemplant-dynamics.git
cd chemplant-dynamics
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 8.3 Run the Application

Development mode:

```bash
python app/main.py
```

Production-style server mode:

```bash
python app/server.py
```

### 8.4 Docker Deployment

The repository includes Docker configuration and a helper guide:

```bash
docker-compose up --build
```

See `DOCKER.md` for more detailed deployment instructions.

## 9. Usage Guidelines

### 9.1 Local Development

The app can be used to inspect process behavior and interactively configure control scenarios. This is suitable for education and rapid prototyping.

### 9.2 Case Exploration

The project’s modular `cases/` structure allows users to:

- evaluate different plant scenarios,
- compare dynamic responses,
- analyze controller tuning strategies,
- test operating points and disturbances.

### 9.3 Research Extension

The codebase is extensible for:

- adding new chemical process models,
- implementing alternative controller strategies,
- adding disturbance and uncertainty analysis,
- comparing model predictions with experimental data.

## 10. Academic and Research Relevance

This project is aligned with engineering research practices because it supports:

- model-based analysis of dynamic systems,
- simulation-driven exploration of process behavior,
- tuning and performance evaluation for control systems,
- reproducible experimentation and software-driven engineering workflows.

It is suitable for:

- undergraduate chemical engineering projects,
- process control coursework,
- capstone or thesis work,
- simulation-based industrial process analysis.

## 11. Typical Workflow

A typical workflow for this project is as follows:

1. Select a case study or define a new process scenario.
2. Instantiate the plant and controller models.
3. Set operating parameters and initial conditions.
4. Run the simulation under disturbance or setpoint changes.
5. Analyze transient response, stability, and performance metrics.
6. Iterate on tuning or model assumptions.
7. Visualize and document the results.

## 12. Key Features

- Dynamic chemical process simulation
- Reactor and thermal process models
- Controller and setpoint modules
- Web-based interactive visualization
- Modular project structure for case studies
- Docker-based deployment support
- Scientific Python ecosystem integration

## 13. Limitations and Future Work

### Current Limitations

- model fidelity is dependent on the assumptions used in each system formulation;
- some configurations may require calibration against experimental data;
- control and operating strategies may be simplified for educational or prototype use;
- process visualization is web-oriented and may require a local runtime environment.

### Potential Future Developments

- expansion to more chemical process units and reactor configurations;
- integration of optimization routines for tuning and operating point selection;
- more advanced multivariable controller strategies;
- uncertainty quantification and sensitivity analysis;
- export of plots and data for formal reporting;
- enhanced benchmarking against industrial process datasets.

## 14. Documentation and Support

- `DOCKER.md`: Docker deployment documentation
- `pyproject.toml`: dependency and project configuration
- `app/`: interactive user interface and application logic
- `models/`: core model implementations
- `cases/`: scenario definitions and reusable study templates

## 15. License and Citation

Please check whether a project license is included in the repository. If a license file is present, use it as the formal licensing basis for reuse and distribution.

If this project is used in a thesis, report, or publication, it is recommended to cite the repository and clearly describe the modeling assumptions and simulation scope.

Example citation format:

```text
Muhammad Hafzul Haikal. ChemPlant Dynamics. GitHub repository, https://github.com/mhafzulhaikal/chemplant-dynamics
```

## 16. Contact

For questions, collaboration opportunities, or academic discussion related to this project, please contact the repository maintainer through the GitHub project page.

---

Version: 0.1.0  
Status: Active development  
Repository: https://github.com/mhafzulhaikal/chemplant-dynamics

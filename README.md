# Nubot : AI tool Builder Backend Services

This project is an AI tool for building, managing, and analyzing chatbots. It features user management, cost tracking, and bot permissions, using Flask (backend), PostgreSQL (relational data), LanceDB (embeddings), and Azure OpenAI (language models).

## Services

 1. main.py
 2. chatSocketService.py

## Features

- **Chatbot Builder**: Create and customize AI chatbots.
- **Chat Log Management**: Store and retrieve user-chatbot interactions.
- **User Management**: Handle multiple users with role-based permissions.
- **Cost Analysis**: Track and report usage costs for the OpenAI API.
- **Bot View/Edit Permissions**: Define view and edit access for bots.
- **Scalable Data Storage**:
  - **PostgreSQL**: For managing user, bot, and log data.
  - **LanceDB**: For vectorized data storage and retrieval.

---

## Technologies Used

- **Backend Framework**: [Python Flask](https://flask.palletsprojects.com/)
- **Database**:
  - **PostgreSQL**: For structured data storage.
  - **LanceDB**: For vector embeddings.
- **AI/LLM API**: [Azure OpenAI](https://azure.microsoft.com/en-us/services/openai/)
- **Authentication**: Role-based access control (RBAC) for permissions and JWT sso.

---

## Installation and Setup

### Prerequisites

- Python 3.9+
- `pip install -r requirement.txt`

### Steps to Setup

1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd <repository-directory>

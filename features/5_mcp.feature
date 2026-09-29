@tutorial
Feature: Step 5 -- MCP

  The README's fifth step: turn on GemDB's MCP server, and an agent can answer
  from the live book by running Python against the same objects the app and
  the notebook use. No export, no API, no description of the schema.

  No language model is involved: what is tested is the protocol an agent
  speaks, against the server GemDB sets up.

  Scenario: an agent answers from the live book over MCP
    When GemDB's MCP server is turned on
    Then the agent is offered a way to run Python

    When the agent asks which plan is losing money
    Then it answers from the live book, as a session of its own would

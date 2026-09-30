Feature: Every surface answers with the same book

  One database, several ways into it, and no second copy of anything. The
  other features each drive one way in; this one puts them side by side and
  requires the same answer.

  The notebook and the snippets in `docs/mcp-questions.md` are the two
  surfaces a browser cannot reach, so they are checked here against the page
  and the payload.

  The figures printed in `docs/mcp-questions.md` are not checked: they
  describe a freshly loaded book, and by now the suite has bought policies and
  filed claims. `tools/make_mcp_questions.py` regenerates them. What is
  checked is that the published code still runs and answers what every other
  surface answers.

  Background:
    Given the app is running

  Scenario: the notebook, the payload and the page agree about the book
    When the notebook is run inside the database
    Then every one of its cells ran
    And I keep its output as "the notebook, cell by cell"

    When I ask for the statistics
    Then the notebook and the payload agree about the size of the book

    When I open the customer picker page
    Then the page states the same number of policyholders
    And I capture "the same figure, on the page"

  Scenario: the published agent snippets still answer what everything else answers
    When I ask for the statistics
    And I run the published book summary
    Then it answers what the JSON surface answers
    And I keep the comparison as "the published snippet against the live book"

    When I run the published loss ratio by tier
    Then it answers what the JSON surface answers for every band
    And I keep the comparison as "loss ratio, two ways"

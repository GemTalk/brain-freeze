Feature: Every surface answers with the same book

  The demo's whole argument in one sentence: there is one database, several
  ways into it, and no second copy of anything. The other features each drive
  one way in. This one puts them side by side and requires the same answer.

  The notebook and the published agent answers are here because they are the
  two surfaces a browser cannot reach. A notebook is run cell by cell by its
  own kernel, and the agent answers are Python snippets a reader is invited to
  paste. Both still have to agree with the page and the payload, and this is
  where that is checked rather than assumed.

  What this does NOT check is the frozen figures printed in the published
  answers. Those describe a freshly seeded book, and by the time this runs the
  suite has bought a policy and filed claims, so they have moved on purpose.
  Replaying them against a fresh seed is `tools/refresh_mcp.py --verify`, over
  the real transport. What is checked here is the more useful half: that the
  code the document publishes still runs, and still answers what every other
  surface answers.

  Background:
    Given the demo is running

  Scenario: the notebook, the payload and the page agree about the book
    When the notebook is run inside the database
    Then every one of its cells ran
    And I keep its output as "the notebook, cell by cell"

    When I ask for the statistics
    Then the notebook and the payload agree about the size of the book

    When I open the customer picker page
    Then the page states the same number of policyholders
    And I capture "the same figure, on the page"

  Scenario: the snippets the demo publishes still answer what everything else answers
    When I ask for the statistics
    And I run the book summary the demo publishes
    Then it answers what the JSON surface answers
    And I keep the comparison as "the published snippet against the live book"

    When I run the loss ratio by tier the demo publishes
    Then it answers what the JSON surface answers for every band
    And I keep the comparison as "loss ratio, two ways"

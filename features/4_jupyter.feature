@tutorial
Feature: Step 4 -- Jupyter

  The README's fourth step: the notebook works on the live objects, and it
  sees the database as of its last transaction -- so a policy bought in the
  browser appears in the notebook only once it refreshes.

  The notebook runs in a session of its own that stays open between steps,
  the way a notebook kernel does.

  Scenario: the notebook sees a policy bought in the browser once it refreshes
    When I open the notebook and run its cells

    When I open the quote page
    And I answer age 9, no migraine, no tension headaches, eating fast, on slushies
    And I accept the Standard plan
    Then I am shown a policy
    And I capture "a policy bought while the notebook is open"

    Then the notebook counts the policies again, and the count has not changed
    When the notebook runs gemdb.refresh()
    Then the notebook counts one more policy
    And the call step 4 of the README shows is the one the notebook made

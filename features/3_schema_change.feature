@tutorial
Feature: Step 3 -- change the schema

  The README's third step, the one the tutorial exists for: add a field to a
  class that already holds 2,172 committed claims, show it in the app, load
  it -- and the app, which never stops, serves it on the next request. The
  old claims still load.

  The change applied is the answer to step 3, features/answers/step3.patch,
  and it is always taken back out afterwards.

  BF-100186 is this scenario's own policy, per the rule at the top of
  `tests/test_app.py`: it writes.

  Scenario: a field added to live data is live in the running app once loaded
    When I open the claim form for BF-100186
    Then the form does not ask which flavour it was
    And I capture "the claim form, before"

    When I make the change step 3 of the README describes
    And I run the commands step 3 of the README shows
    Then each one prints what the README says it prints

    When I open the claim form for BF-100186
    Then the form asks which flavour it was, and what was on top
    And the app was never restarted
    And I capture "the claim form, after loading"

    When I file a claim for Mint choc chip, topped with Sprinkles and Hot fudge, pain 6, lasting Half a minute to two
    Then the decision names the flavour and the toppings
    And I capture "a claim that records the flavour"

    When I open claim CLM-001285 on BF-100539, filed before the change
    Then it still loads, and names no flavour
    And I capture "a claim from before the change"

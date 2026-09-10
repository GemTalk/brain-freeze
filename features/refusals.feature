Feature: The refusals, and being told why

  Three ways a claim is refused before anyone fills the form in, and three
  different sentences saying which one it is. None of them needs setting up:
  the seeded book already holds a policy whose cover ended, one that has spent
  its four approvals for the year, and a hundred-odd whose terms have not
  begun yet. Nothing here files a claim, so nothing here can dirty the book --
  these are the cheapest scenarios in the suite and the ones most likely to
  still work next year.

  The pair worth the trouble is the last one. A policy whose term has not
  started never lapsed, and telling its customer that it did is a mistake this
  demo has made before. So the two refusals are read against each other rather
  than one at a time, and each is checked against the reason the rules
  themselves give, so the screen and the adjudicator cannot drift apart.

  Background:
    Given the demo is running

  Scenario: cover that has ended is named as a lapse
    Given the policy BF-100746
    Then the policy page marks cover lapsed on 2026-07-12
    When the customer goes to file a claim
    Then the claim is refused before a word is typed
    And the refusal reads "Cover on this policy ended on 2026-07-12. Anything filed now is refused."
    And the rules give "Policy lapsed" as the reason there is no cover
    And I capture "cover on this policy ended"

  Scenario: the year's allowance, once spent, is spent
    Given the policy BF-100539
    And the year's approvals are already spent
    Then the policy page shows all 4 approvals used
    And the policy still has cover
    When the customer goes to file a claim
    Then the claim is refused before a word is typed
    And the refusal reads "This policy has used all 4 approvals for the year. A new claim is refused until it renews."
    And I capture "the year's allowance is spent"

  Scenario: a term that has not begun is not a lapse
    Given a policy whose cover has not started yet
    Then the policy page marks cover as starting on the day the term begins
    When the customer goes to file a claim
    Then the claim is refused before a word is typed
    And the refusal reads "Cover on this policy does not start until <the day cover starts>. Anything filed now is refused."
    And the rules give "Event outside policy term" as the reason there is no cover
    And I capture "cover has not started yet"

  Scenario: the two absences of cover are told apart
    Given the policy BF-100746
    When the customer goes to file a claim
    And that refusal is kept as "the lapse"

    Given a policy whose cover has not started yet
    When the customer goes to file a claim
    And that refusal is kept as "the term that has not begun"

    Then the two refusals are not the same sentence
    And "the lapse" speaks of cover that ended, and "the term that has not begun" does not
    And neither refusal names a date the policy does not have
    And the rules tell the two apart as well

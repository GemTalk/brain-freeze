Feature: Changing a policy while the app is serving it

  The demo's central claim, and the only scenario that can show it.

  Nothing else in this repo captures this. The in-database tests can pin the
  mechanism but not the beat, because a session sees its own writes
  immediately and a test running inside the database cannot start a second
  one. So this is the only place the promise is demonstrated rather than
  argued.

  `lapse.py` opens the same objects from a session of its own and commits. It
  does not know the app exists. The app takes a new view before each request,
  so it sees the next one -- no restart, no reload, no polling.

  Background:
    Given the demo is running

  Scenario: a policy lapsed from a shell turns up in the browser, and turns back
    Given I open the policy BF-100184
    Then the policy is shown as active
    And I capture "before -- active"

    When I open the claim form for BF-100184
    Then I am invited to file a claim
    And I capture "before -- the claim form is open"

    When BF-100184 is lapsed from a session of its own
    And I re-open the policy BF-100184
    Then the policy is shown as lapsed
    And the app was never restarted
    And I capture "after -- lapsed, with no restart"

    When I open the claim form for BF-100184
    Then I am told cover has ended
    And I capture "after -- the claim form refuses"

    When BF-100184 is reinstated from a session of its own
    And I re-open the policy BF-100184
    Then the policy is shown as active
    And I capture "reinstated -- back where it started"

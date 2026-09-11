Feature: The same policies over curl

  Everything the browser shows is also readable by a script, from the same
  objects, with no second model behind it. That is the whole claim of this
  surface, and it is checkable: ask the JSON side for a policy and the HTML
  side for the same policy, and the figures have to agree.

  Two properties are worth stating on their own.

  Money is an exact decimal string -- "171.00", never 171.0 and never 17100.
  A float would put back at the boundary the two answers exact money exists
  to remove, and integer cents would be exact but would make every reader
  divide by a hundred. A string is the same text the model already reads, so
  a figure goes back in unchanged.

  And the surface is read-only. Pricing a quote is a POST because it carries
  a body, not because it writes: nothing here commits, so a script can be
  pointed at a live demo without any way to spoil it.

  The evidence here is the payloads rather than screenshots. There is nothing
  to photograph, and what a reader wants afterwards is the exact bytes the
  run was given.

  Background:
    Given the demo is running

  Scenario: a script reads the questions, answers them, and is quoted
    When I ask for the questions
    Then the questions name the five things the price depends on
    And every question offers the values the model will accept
    And I keep the payload as "the questions a script is given"

    When I answer them exactly as they were offered
    Then I am quoted a score, a band and three priced plans
    And the answers come back with the price
    And every figure that is money is an exact decimal string
    And I keep the payload as "the quote that came back"

    When I send an answer the model does not accept
    Then I am refused with a message naming the field at fault
    And I keep the payload as "a refusal a script can read"

  Scenario: the book, one policy, and one claim, all from the same objects
    When I ask for the whole book
    Then the book holds every policy the seed made
    And every figure that is money is an exact decimal string
    And I keep the payload as "the whole book"

    When I ask for the policy BF-100539
    Then the policy carries its whole history, treats and claims alike
    And every figure that is money is an exact decimal string
    And I keep the payload as "one policy and its history"

    When I open the same policy in the browser
    Then the page and the payload agree about what it has been paid
    And I capture "the same policy, in a browser"

    When I ask for a claim on that policy by its id alone
    Then the claim comes back with the terms it was judged by
    And every figure that is money is an exact decimal string
    And I keep the payload as "one claim, found by id alone"

    When I ask for a policy that does not exist
    Then I am told there is no such policy, in JSON rather than in HTML

  Scenario: the book-level figures are the ones the analysis gives
    When I ask for the statistics
    Then the loss ratio is reported by tier and by plan
    And the refusals are counted by reason
    And every figure that is money is an exact decimal string
    And I keep the payload as "what the book looks like from above"

    When I ask for the whole book again
    Then the statistics agree with the policies about how many there are

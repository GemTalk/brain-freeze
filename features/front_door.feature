Feature: Finding one customer among nine hundred

  The policies page lists the book, and the whole book is too big for one page:
  rendering all 900 rows takes the best part of a minute, because Grail runs
  each template in a forked green thread. So the page states the total and
  shows a window onto it.

  That makes two things load-bearing. The count has to be the book's, not the
  window's. And there has to be a way to reach a policy by id, because paging
  to BF-100539 fifty rows at a time is a wait.

  Typing a whole policy id goes straight to that policy, because a search with
  one answer should not make you click the answer.

  Background:
    Given the app is running

  Scenario: the book is paged, and the count is the book's count
    When I open the customer picker page
    Then the page says how many policyholders there are
    And it shows a window onto the book rather than all of it
    And I capture "the first page of the book"

    When I go to the next page
    Then I am shown the customers after the ones I have seen
    And the page still says how many policyholders there are
    And I capture "the second page"

    When I go back to the previous page
    Then I am shown the customers I started with

  Scenario: a policy id typed into the box goes straight to that policy
    When I open the customer picker page
    And I look up BF-100539
    Then I am taken to that policy without having to choose it
    And I capture "found by typing the id"

    When I open the customer picker page
    And I look up BF-1005
    Then I am shown only the policies whose ids contain it
    And I capture "a partial id narrows the list"

    When I open the customer picker page
    And I look up BF-999999
    Then I am told nothing matches, rather than shown an empty table
    And I capture "nothing matches"

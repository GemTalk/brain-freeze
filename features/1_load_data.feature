@tutorial @no-seed @no-app
Feature: Step 1 -- load data

  The README's first step, run the way it says to run it, against a database
  nothing of ours has touched. The commands are read out of the README, and so
  is what they are supposed to print: if the two part company, this fails
  before a reader finds out.

  Scenario: the sample book goes in as ordinary Python objects
    Then nothing of ours is in the database yet

    When I run the commands step 1 of the README shows
    Then each one prints what the README says it prints
    And the book holds 900 policyholders and 2172 claims, as objects

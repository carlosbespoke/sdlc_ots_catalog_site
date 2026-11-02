Loan accounts can still be opened bare: `LoanAccountService.createLoanAccount(UUID, String)`, behind `POST /api/v1/loan-accounts`, opens an account with no guarantors or collateral and leaves the borrower's other applications pending. Make `createSecuredLoanAccount(SecuredOriginationRequest)` the only way to open one.

In one transaction it should:
- open the account from the approved application with today's checks and product terms (`IllegalArgumentException` on failure);
- attach every requested guarantor (customer, type, amount) and collateral item (all `CollateralRequest` details);
- set `territoryCode` and `originationReference` = `<territoryCode>/<lead guarantor customer id>/<account number>`, where the lead (`leadGuarantorCustomerId`) must be an `INDIVIDUAL` guarantor, or `CORPORATE` for a `corporateGroup`, else `IllegalArgumentException`;
- withdraw the borrower's other pending applications, or the group's (applicant plus `groupCustomerIds`), through `LoanApplicationService`, pointing them at the account and leaving everything else untouched;
- write one `LoanOriginationAudit` (application, analyst, territory, group flag, withdrawn count).

A rejected request saves nothing.

Then retire the bare path: remove `createLoanAccount(UUID, String)` and `LoanAccountCreateRequest`, and have `POST /api/v1/loan-accounts` take a `SecuredOriginationRequest` and still answer 201 with the account. All existing loan-service tests must pass (`mvn -pl loan/loan-service -am test`); don't edit the poms.

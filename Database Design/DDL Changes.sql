ALTER TABLE PRODUCT
MODIFY NAME VARCHAR2(150) ;

ALTER TABLE PRODUCT 
ADD PRICE NUMBER NOT NULL;

ALTER TABLE PURCHASE_ORDER
DROP COLUMN EXPECTED_DELIVERY_DATE;

ALTER TABLE OFFER
DROP COLUMN MINIMUM_PRICE_PURCHASED;

ALTER TABLE ADVERTISEMENT
DROP COLUMN DISPLAY_PREFERENCE;

ALTER TABLE CUSTOMER_ORDER 
ADD SELLER_ID NUMBER NOT NULL;

ALTER TABLE CUSTOMER_ORDER 
ADD CONSTRAINT ORDER_FK2 FOREIGN KEY(SELLER_ID) REFERENCES SELLER(SELLER_ID);

ALTER TABLE PURCHASE_ORDER
ADD PAYMENT_METHOD VARCHAR2(20) NOT NULL;

ALTER TABLE CUSTOMER_ORDER
DROP COLUMN PAYMENT_METHOD;

ALTER TABLE OFFER 
DROP COLUMN MINIMUM_QUANTITY_PURCHASED;

ALTER TABLE OFFER
ADD MINIMUM_QUANTITY_PURCHASED NUMBER NOT NULL;

from django.shortcuts import render
from django.db import connections
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.models import User
from django.shortcuts import reverse
from PIL import Image
from django.conf import settings
import threading
import math
import io
import random
from datetime import timedelta, date
import info

def deliveryEmployeeSelection(orderID):
    orderID = int(orderID)
    query = """SELECT HAVERSINE(ORDER_ID) FROM CUSTOMER_ORDER WHERE ORDER_ID = (:orderID)"""
    with connections['oracle'].cursor() as cursor:
        cursor.execute(query, {'orderID':orderID});
        id = cursor.fetchall()[0][0]
    return id

def accountBalance(email, type):
    with connections['oracle'].cursor() as cursor:
        if type == 'customer':
            cursor.execute("SELECT WALLET_BALANCE(CUSTOMER_ID , 'CUSTOMER') FROM CUSTOMER WHERE EMAIL_ID = :email", {'email':email})
            balance = cursor.fetchall()[0][0]
            if balance == None:
                return 0
            else:
                return float(balance)
        elif type == 'seller':
            cursor.execute("SELECT WALLET_BALANCE(SELLER_ID , 'SELLER') FROM SELLER WHERE EMAIL_ID = :email", {'email': email})
            balance = cursor.fetchall()[0][0]
            if balance == None:
                return 0
            else:
                return float(balance)

def getAdverts(request):
    query = """SELECT PRODUCT_ID, SELLER_ID, ADVERTISEMENT_NUMBER, PICTURE FROM ADVERTISEMENT
               WHERE END_DATE>SYSDATE"""
    with connections['oracle'].cursor() as cursor:
        cursor.execute(query)
        results = cursor.fetchall()
        imagePaths = []
        for result in results:
            imagePath = "http://{}/static/images/productImages/advert{}_{}_{}.jpg".format(request.META['HTTP_HOST'], result[0], result[1], result[2])
            imageFile = open(settings.BASE_DIR+"\\static\\images\\productImages\\advert{}_{}_{}.jpg".format(result[0], result[1], result[2]),'wb')
            imageFile.write( result[3].read() )
            imageFile.close()
            imagePaths.append(imagePath)
        if len(imagePaths)<4:
            placeHolder = "http://{}/static/images/productImages/{}".format(request.META['HTTP_HOST'], 'advertisementPlaceholder.jpg')
            imagePaths.append(placeHolder)
        adverts = []
        for i in range(8):
            index = random.randrange(0, len(imagePaths))
            adverts.append(imagePaths[index])
        return adverts

def ratingUtility(num):
    if num<=0:
        return 0
    elif num>=1:
        return 1
    else:
        return num

def make_image_square(img):
    width, height = img.size
    size = max(width, height)
    new_img = Image.new('RGB', (size, size), (255, 255, 255))
    new_img.paste(img, (int((size - width) / 2), int((size - height) / 2)))
    return new_img

def check_productID(id):
    with connections['oracle'].cursor() as cursor:
        cursor.execute("SELECT PRODUCT_ID FROM PRODUCT WHERE PRODUCT_ID = :id", {'id' :id})
        if(len(cursor.fetchall()) != 0):
            if(cursor.fetchall()[0][0] == id):
                return True
        else :
            return False

def accountType(email):
    with connections['oracle'].cursor() as cursor:
        cursor.execute("SELECT SELLER_ID FROM SELLER WHERE EMAIL_ID =:email", {"email": email})
        results = cursor.fetchall()
        if(len(results) == 0):
            cursor.execute("SELECT CUSTOMER_ID FROM CUSTOMER WHERE EMAIL_ID =:email", {"email": email})
            results = cursor.fetchall()
            if(len(results) == 0):
                cursor.execute("SELECT EMPLOYEE_ID FROM EMPLOYEE WHERE EMAIL_ID =:email", {"email": email})
                emID = cursor.fetchall()[0][0]
                cursor.execute("SELECT EMPLOYEE_ID FROM DELIVERY_GUY WHERE EMPLOYEE_ID =:emID", {"emID" : emID})
                results = cursor.fetchall()
                if(len(results) == 0):
                     cursor.execute("SELECT EMPLOYEE_ID FROM CUSTOMER_CARE_EMPLOYEE WHERE EMPLOYEE_ID =:emID", {"emID" : emID})
                     results = cursor.fetchall()
                     if(len(results) == 0):
                         cursor.execute("SELECT EMPLOYEE_ID FROM ADMIN WHERE EMPLOYEE_ID =:emID", {"emID" : emID})
                         results = cursor.fetchall()
                         if(len(results) != 0):
                             return 'admin'
                     else :
                         return 'customerCare'
                else:
                    return 'deliveryGuy'
            else:
                return 'customer'
        else:
            return 'seller'

def item_page(request, product_id, seller_id):
    isloggedin = False
    acType = 'none'
    iscustomerlogin = False
    acBal = 0
    if request.session.has_key('useremail'):
        isloggedin = True
        acType = accountType(request.session['useremail'])
        if acType == 'customer':
            iscustomerlogin = True
            acBal = accountBalance(request.session['useremail'], acType)

    if request.method == 'POST' and iscustomerlogin:
        formIdentity = request.POST.get('formIdentity')
        if formIdentity == 'orderForm':
            quantity = int( request.POST.get('orderQuantity') )
            paymentMethod = request.POST.get('paymentMethod')

            query = """SELECT ITEM_NUMBER FROM PRODUCT_UNIT WHERE PRODUCT_ID = TO_NUMBER(:pid)
                       AND SELLER_ID = TO_NUMBER(:sid) AND LOWER(STATUS) = 'not sold'"""
            data = {'pid': product_id, 'sid': seller_id}

            with connections['oracle'].cursor() as cursor:
                cursor.execute(query, data)
                itemNumbers = cursor.fetchall()
                if( len(itemNumbers) >= int(quantity) ):
                    for i in range( int(quantity) ):
                        inum = itemNumbers[i][0]
                        query = """UPDATE PRODUCT_UNIT SET STATUS = 'Sold' WHERE
                                   PRODUCT_ID = TO_NUMBER(:pid) AND SELLER_ID = TO_NUMBER(:sid)
                                   AND ITEM_NUMBER = TO_NUMBER(:inum)"""
                        data = {'pid': product_id, 'sid': seller_id, 'inum': inum}
                        cursor.execute(query, data)

                    query = "SELECT ORDER_ID_SEQ.NEXTVAL FROM DUAL"
                    cursor.execute(query)
                    orderID = cursor.fetchall()[0][0]

                    query = """INSERT INTO CUSTOMER_ORDER VALUES(TO_NUMBER(:oid),
                               (SELECT CUSTOMER_ID FROM CUSTOMER WHERE EMAIL_ID = :email),
                               SYSDATE, TO_NUMBER(:sid) )"""
                    data = { 'oid': orderID, 'sid': seller_id,
                             'email': request.session['useremail'] }
                    cursor.execute(query, data)

                    query = """INSERT INTO PURCHASE_ORDER VALUES(TO_NUMBER(:oid),
                              TO_NUMBER(:empID), NULL, 'Not Delivered', :pm)"""
                    data = { 'oid': orderID, 'empID': deliveryEmployeeSelection(orderID),
                             'pm': paymentMethod }
                    cursor.execute(query, data)

                    for i in range( int(quantity) ):
                        inum = itemNumbers[i][0]
                        query = """INSERT INTO ORDERED_ITEMS VALUES(TO_NUMBER(:pid),
                                   TO_NUMBER(:sid), TO_NUMBER(:oid), TO_NUMBER(:inum)) """
                        data = {'pid': product_id, 'sid': seller_id, 'oid': orderID,
                                'inum': inum}
                        cursor.execute(query, data)

                    cursor.execute("commit")

            return HttpResponseRedirect("http://{}/product/item/{}/{}".format(request.META['HTTP_HOST'],product_id, seller_id))
        elif formIdentity == 'reviewForm':
            rating = request.POST.get("starRating")
            reviewDescription = request.POST.get("reviewDescription")
            with connections['oracle'].cursor() as cursor:
                query = """SELECT RATING FROM REVIEW WHERE (PRODUCT_ID = :product_id AND SELLER_ID = :seller_id AND CUSTOMER_ID =
                          (SELECT CUSTOMER_ID FROM CUSTOMER WHERE EMAIL_ID = :email) )"""
                data = {'product_id' :product_id,'seller_id':seller_id, 'email':request.session['useremail']}
                cursor.execute(query, data)
                result = cursor.fetchall()

                if(len(result) == 0):
                    query = """INSERT INTO REVIEW VALUES (TO_NUMBER(:product_id), TO_NUMBER(:seller_id), (SELECT CUSTOMER_ID FROM CUSTOMER
                               WHERE EMAIL_ID = :email),SYSDATE ,TO_NUMBER(:rating), :description)"""
                    data = {'product_id' :product_id,'seller_id':seller_id, 'email':request.session['useremail'], 'rating':rating, 'description':reviewDescription}
                    cursor.execute(query, data)
                    cursor.execute("COMMIT")
                else:
                    query = """UPDATE REVIEW SET REVIEW_DATE = SYSDATE ,RATING = TO_NUMBER(:rating), DESCRIPTION = :description  WHERE (PRODUCT_ID = :product_id AND SELLER_ID = :seller_id AND CUSTOMER_ID =
                              (SELECT CUSTOMER_ID FROM CUSTOMER WHERE EMAIL_ID = :email) )"""
                    data = {'product_id' :product_id,'seller_id':seller_id, 'email':request.session['useremail'], 'rating':rating, 'description':reviewDescription}
                    cursor.execute(query, data)
                    cursor.execute("COMMIT")
            return HttpResponseRedirect("http://{}/product/item/{}/{}".format(request.META['HTTP_HOST'],product_id, seller_id))
        elif formIdentity == 'cartForm':
            cartQuantity = request.POST.get('cartQuantity')
            with connections['oracle'].cursor() as cursor:
                query = """SELECT QUANTITY FROM CART_ITEM WHERE (PRODUCT_ID = :product_id AND SELLER_ID = :seller_id AND CUSTOMER_ID =
                          (SELECT CUSTOMER_ID FROM CUSTOMER WHERE EMAIL_ID = :email) )"""
                data = {'product_id' :product_id,'seller_id':seller_id, 'email':request.session['useremail']}
                cursor.execute(query, data)
                result = cursor.fetchall()

                if(len(result) == 0):
                    query = """INSERT INTO CART_ITEM VALUES (TO_NUMBER(:product_id), TO_NUMBER(:seller_id), (SELECT CUSTOMER_ID FROM CUSTOMER
                               WHERE EMAIL_ID = :email),TO_NUMBER(:cartQuantity))"""
                    data = {'product_id' :product_id,'seller_id':seller_id, 'email':request.session['useremail'], 'cartQuantity':cartQuantity}
                    cursor.execute(query, data)
                    cursor.execute("COMMIT")
                else:
                    query = """UPDATE CART_ITEM SET QUANTITY = TO_NUMBER(:cartQuantity) WHERE (PRODUCT_ID = :product_id AND SELLER_ID = :seller_id AND CUSTOMER_ID =
                              (SELECT CUSTOMER_ID FROM CUSTOMER WHERE EMAIL_ID = :email) )"""
                    data = {'product_id' :product_id,'seller_id':seller_id, 'email':request.session['useremail'],'cartQuantity':cartQuantity}
                    cursor.execute(query, data)
                    cursor.execute("COMMIT")
            return HttpResponseRedirect("http://{}/product/item/{}/{}".format(request.META['HTTP_HOST'],product_id, seller_id))

    with connections['oracle'].cursor() as cursor:
        query =  """SELECT P.NAME PRODUCT_NAME, P.DESCRIPTION, C.CATEGORY_NAME, P.EXPECTED_TIME_TO_DELIVER, S.NAME SELLER_NAME, COUNT(PU.ITEM_NUMBER) IN_STOCK, AVG(R.RATING) RATING, P.PRICE FROM
                    PRODUCT P JOIN CATEGORY C USING(CATEGORY_ID) JOIN SELLER S ON(S.SELLER_ID=P.SELLER_ID) LEFT OUTER JOIN PRODUCT_UNIT PU
                    ON ( PU.PRODUCT_ID=P.PRODUCT_ID AND PU.SELLER_ID=P.SELLER_ID AND LOWER(PU.STATUS)='not sold' ) LEFT OUTER JOIN REVIEW R
                    ON(R.SELLER_ID=P.SELLER_ID AND R.PRODUCT_ID=P.PRODUCT_ID )
                    WHERE (P.PRODUCT_ID =:product_id AND P.SELLER_ID = :seller_id )
                    GROUP BY P.NAME, P.DESCRIPTION, CATEGORY_NAME, EXPECTED_TIME_TO_DELIVER,S.NAME, P.PRICE"""
        data = {'product_id' :product_id,'seller_id':seller_id}
        print(data)
        cursor.execute(query, data)
        result = cursor.fetchall()
        print(result)
        productName = result[0][0]
        productDescription = result[0][1]
        productCategory = result[0][2]
        rating = result[0][6]
        price = result[0][7]
        sellerName = result[0][4]
        inStock = result[0][5]
        deliveryTime = result[0][3]
        query = """SELECT FEATURE_DESCRIPTION FROM PRODUCT_FEATURE WHERE PRODUCT_ID = :product_id AND SELLER_ID = :seller_id"""
        cursor.execute(query, data)
        result = cursor.fetchall()
        features = []

        for i in range(len(result)):
            features.append(result[i][0])

        query = """SELECT PERCENTAGE_DISCOUNT, END_DATE, MINIMUM_QUANTITY_PURCHASED FROM OFFER WHERE
                   (PRODUCT_ID = :product_id AND SELLER_ID = :seller_id AND START_DATE<= SYSDATE AND SYSDATE <= END_DATE)"""
        cursor.execute(query, data)
        result = cursor.fetchall()
        offers = []
        for i in range(len(result)):
            temp = []
            for j in range(len(result[i])):
                temp.append(result[i][j])
            offers.append(temp)

        query = """SELECT NAME, RATING, DESCRIPTION, TO_CHAR(REVIEW_DATE,'DD MON YYYY') FROM REVIEW JOIN (SELECT (FIRST_NAME||' '||LAST_NAME)NAME,
                   CUSTOMER_ID FROM CUSTOMER) USING (CUSTOMER_ID) WHERE (PRODUCT_ID = :product_id AND SELLER_ID = :seller_id )"""
        cursor.execute(query, data)
        result = cursor.fetchall()
        reviews = []
        for i in range(len(result)):
            temp = []
            for j in range(len(result[i])):
                temp.append(result[i][j])
            if temp[2] == None:
                temp[2] = ''
            reviews.append(temp)
        query = """SELECT PICTURE FROM PRODUCT_PICTURE WHERE (PRODUCT_ID = :product_id AND SELLER_ID = :seller_id )"""
        cursor.execute(query, data)
        result = cursor.fetchall()
        pictures = []
        for i in range(len(result)):
            imagePath = "http://{}/static/images/productImages/{}_{}_{}.jpg".format(request.META['HTTP_HOST'], product_id, seller_id, i+1)
            imageFile = open(settings.BASE_DIR+"\\static\\images\\productImages\\{}_{}_{}.jpg".format(product_id, seller_id, i+1),'wb')
            imageFile.write( result[i][0].read() )
            imageFile.close()
            pictures.append(imagePath)
        if( len(pictures)==1 ):
            pictures.append( pictures[0] )

        query = "SELECT COUNT(*) FROM REVIEW WHERE PRODUCT_ID = :product_id AND SELLER_ID = :seller_id"
        cursor.execute(query, {'product_id': product_id, 'seller_id': seller_id})
        reviewCount = int( cursor.fetchall()[0][0] )

        ratingHTML = '<h3 class="text-warning">'
        if rating is None:
            rating = 0
        rating = float(rating)
        temp = rating
        count = 0
        while temp>=1 :
            ratingHTML += '\n<i class="fa fa-star" aria-hidden="true"></i>'
            temp -= 1
            count += 1
        if temp>0 and temp<1:
            ratingHTML += '\n<i class="fa fa-star-half-o" aria-hidden="true"></i>'
            temp -= 1
            count += 1
        while count < 5:
            ratingHTML += '\n<i class="fa fa-star-o" aria-hidden="true"></i>'
            count += 1
        if reviewCount == 1:
            ratingHTML += '&nbsp;&nbsp;<span style="font-size: 12px">1 review</span>'
        else:
            ratingHTML += '&nbsp;&nbsp;<span style="font-size: 12px">{} reviews</span>'.format(reviewCount)
        ratingHTML += '\n</h3>'

        featureListHTML = ""
        for feature in features:
            featureListHTML += "<li>"
            featureListHTML += feature
            featureListHTML += "</li>"

        offerListHTML = ""
        offerDisplay = 'block'
        if len(offers) == 0:
            offerDisplay = 'none'
        else:
            for offer in offers:
                offerListHTML += "<li style='margin-bottom:8px'>"
                offerListHTML += """<span style='color: #0275d8; font-size: 20px;'>
                                    <strong>
                                    <span name="discountPercentage">{}</span>% discount till {}.</strong></span>
                                    <br />
                                    Conditions: <br />
                                    <i class="fa fa-hand-o-right" aria-hidden="true"></i>&nbsp; <span name="minQuan">{}</span> or more units bought""".format(offer[0], offer[1], offer[2])
                offerListHTML += "</li>"

        inStockHTML = ''
        if int(inStock) > 0:
            inStockHTML = """<h6 class="text-success">
                                <i class="fa fa-check-circle" aria-hidden="true"></i> In Stock
                                <small> {} units</small>
                            </h6>""".format(inStock)
        else:
            inStockHTML = """<h6 class="text-danger">
                                <i class="fa fa-times-circle" aria-hidden="true"></i> Out of Stock
                            </h6>"""

        reviewsHTML = ""
        if len(reviews) == 0:
            reviewsHTML = """<h4 style="font-family: 'Vollkorn', serif; font-weight: 600">Be the first one to review !!!</h4>"""
        else:
            for review in reviews:
                starHTML = ""
                for j in range(1, int(review[1])+1):
                    starHTML += '<li class="fa fa-star" style="color: #ffb300;"></li>'
                for j in range(int(review[1])+1, 6):
                    starHTML += '<li class="fa fa-star" style="color: rgb(100, 0, 0);"></li>'
                reviewsHTML += """<li style="background-color: #f2f8f8;" class="list-group-item">
                                    <h6 class="card-title" style="color: #0275d8">{}</h6>
                                    <p class="card-text" style="margin-bottom: 2px;">{}</p>
                                    <ul class="rating" style="padding-left: 0;">
                                        {}
                                    </ul>
                                    <br />
                                    <small class="text-muted">{}</small>
                                  </li>""".format(review[0], review[2], starHTML, review[3])

        productImageHTML = ""
        productImageHTML2 = ""
        for i in range(0, len(pictures)):
            if i == 0:
                productImageHTML += """<div class="carousel-item active">
                                            <img class="w-100 d-block" style="width: 100%; height: auto" src="{}" alt="Slide Image" style="width: auto; height: 350px">
                                       </div>""".format(pictures[i])
                productImageHTML2 += '<li data-target="#carousel-1" data-slide-to="{}" class="active"></li>'.format(i)
            else:
                productImageHTML += """<div class="carousel-item">
                                            <img class="w-100 d-block" style="width: 100%; height: auto" src="{}" alt="Slide Image" style="width: auto; height: 350px">
                                       </div>""".format(pictures[i])
                productImageHTML2 += '<li data-target="#carousel-1" data-slide-to="{}"></li>'.format(i)

    verticalMargin = ''
    if( rating > 0 ):
        verticalMargin = '6.5px'
    else:
        verticalMargin = '9px'

    adverts = getAdverts(request)

    deliveryTime = date.today() + timedelta(days=int(deliveryTime))

    data = {'iscustomerlogin': iscustomerlogin, 'isloggedin': isloggedin, 'accountType': acType,
            'productName': productName, 'productDescription': productDescription,
            'productCategory': productCategory, 'featureListHTML': featureListHTML,
            'offerListHTML': offerListHTML, 'ratingHTML': ratingHTML, 'sellerName': sellerName,
            'inStockHTML': inStockHTML, 'deliveryTime': deliveryTime, 'offerDisplay': offerDisplay,
            'reviewsHTML': reviewsHTML, 'productImageHTML': productImageHTML,
            'productImageHTML2': productImageHTML2, 'productID': product_id, 'inStock': inStock,
            'price': price, 'verticalMargin': verticalMargin, 'advert1': adverts[0], 'advert2': adverts[1],
            'advert3': adverts[2], 'advert4': adverts[3], 'advert5': adverts[4], 'advert6': adverts[5],
            'advert7': adverts[6], 'advert8': adverts[7], 'extraBreak': len(productName)<57,
            'acBal': acBal, 'deliveryCharge': info.serviceChargePercentage}

    return render(request, 'item.html', data)

def edit_product_page(request, product_id, seller_id):
    isloggedin = False
    acType = 'none'
    if request.session.has_key('useremail'):
        isloggedin = True
        acType = accountType(request.session['useremail'])
        if acType != 'seller':
            return HttpResponseRedirect(reverse('home_page'))
    else:
        return HttpResponseRedirect(reverse('home_page'))

    adverts = getAdverts(request)

    with connections['oracle'].cursor() as cursor:
        query = """SELECT NAME, CATEGORY_ID, DESCRIPTION, EXPECTED_TIME_TO_DELIVER, PRICE FROM PRODUCT
                   WHERE PRODUCT_ID = :pid AND SELLER_ID = :sid"""
        data = {'pid': product_id, 'sid': seller_id}
        cursor.execute(query, data)
        productInfo = cursor.fetchall()

        name = productInfo[0][0]
        categoryID = productInfo[0][1]
        description = productInfo[0][2]
        deliveryTime = productInfo[0][3]
        price = productInfo[0][4]

        query = """SELECT CATEGORY_NAME FROM CATEGORY WHERE CATEGORY_ID = :cid"""
        data = {'cid': int(categoryID)}
        cursor.execute(query, data)
        categoryName = cursor.fetchall()[0][0]

        query = """SELECT COUNT(*) FROM PRODUCT_UNIT WHERE PRODUCT_ID = :pid AND SELLER_ID = :sid
                   AND LOWER(STATUS) = 'not sold'"""
        cursor.execute(query, {'pid': int(product_id), 'sid': int(seller_id)})
        stock = cursor.fetchall()[0][0]

        query = """SELECT CATEGORY_NAME FROM CATEGORY"""
        cursor.execute(query)
        allCategories = cursor.fetchall()
        allCategories = [c[0] for c in allCategories]

        query = "SELECT FEATURE_DESCRIPTION FROM PRODUCT_FEATURE WHERE PRODUCT_ID = :pid AND SELLER_ID = :sid"
        data = {'pid': product_id, 'sid': seller_id}
        cursor.execute(query, data)
        features = cursor.fetchall()
        features = [f[0] for f in features]

        emptySlots = 6 - len(features)
        for i in range(emptySlots):
            features.append('')

        featuresHTML = ""
        for i in range(len(features)):
            if len(features[i]) > 0:
                displayStyle = 'block'
            else:
                displayStyle = 'none'
            featuresHTML += """<div style="display: {}" id="feature{}" class="col-lg-12">
                                 <div class="form-group">
                                   <input maxlength="100" name="feature{}" class="form-control customInput" type="text" placeholder="feature {}" value="{}">
                                 </div>
                               </div>""".format(displayStyle, i+1, i+1, i+1, features[i])

    if request.method == 'POST':
        new_name = request.POST.get("productName")
        new_price = int(request.POST.get("productPrice"))
        new_deliveryTime = request.POST.get("deliveryTime")
        new_category = request.POST.get("chosenCategory")
        new_description = request.POST.get("description")

        with connections['oracle'].cursor() as cursor:
            query = """SELECT CATEGORY_ID FROM CATEGORY WHERE CATEGORY_NAME = :cname"""
            cursor.execute(query, {'cname': new_category})
            new_category = cursor.fetchall()[0][0]

            if price!=new_price:
                query = """UPDATE PRODUCT SET
                             NAME = :name,
                             CATEGORY_ID = :cid,
                             DESCRIPTION = :description,
                             EXPECTED_TIME_TO_DELIVER = :new_deliveryTime,
                             PRICE = :price,
                             LAST_UPDATE = SYSDATE
                           WHERE PRODUCT_ID = :pid AND SELLER_ID = :sid"""
                data = {'name': new_name, 'cid': int(new_category), 'description': new_description,
                        'new_deliveryTime': new_deliveryTime, 'price': new_price, 'pid': int(product_id),
                        'sid': int(seller_id)}
                cursor.execute(query, data)

            elif new_name!=name or categoryID!=new_category or description!=new_description or deliveryTime!=new_deliveryTime:
                query = """UPDATE PRODUCT SET
                             NAME = :name,
                             CATEGORY_ID = :cid,
                             DESCRIPTION = :description,
                             EXPECTED_TIME_TO_DELIVER = :new_deliveryTime,
                             LAST_UPDATE = SYSDATE
                           WHERE PRODUCT_ID = :pid AND SELLER_ID = :sid"""
                data = {'name': new_name, 'cid': int(new_category), 'description': new_description,
                        'new_deliveryTime': new_deliveryTime, 'pid': int(product_id),
                        'sid': int(seller_id)}
                cursor.execute(query, data)

        new_quantityInStock = request.POST.get("quantityInStock")

        if new_quantityInStock!=stock:
            pass

        new_feature1 = request.POST.get("feature1")
        new_feature2 = request.POST.get("feature2")
        new_feature3 = request.POST.get("feature3")
        new_feature4 = request.POST.get("feature4")
        new_feature5 = request.POST.get("feature5")
        new_feature6 = request.POST.get("feature6")
        new_features = (new_feature1, new_feature2, new_feature3, new_feature4, new_feature5, new_feature6)

        featuresChanged = False
        for i in range(len(features)):
            if features[i]!=new_features[i]:
                featuresChanged = True
                break

        if featuresChanged:
            with connections['oracle'].cursor() as cursor:
                query = "DELETE FROM PRODUCT_FEATURE WHERE PRODUCT_ID = :pid AND SELLER_ID = :sid"
                data = {'pid': int(product_id), 'sid': int(seller_id)}
                cursor.execute(query, data)
                for i in range(0, len(new_features)):
                    if len(new_features[i]) > 0:
                        query = "INSERT INTO PRODUCT_FEATURE VALUES(:pid, :sid, :fn, :description)"
                        data = {'pid': int(product_id), 'sid': int(seller_id), 'fn': i+1,
                                'description': new_features[i]}
                        cursor.execute(query, data)

        reverseStr = 'http://'+request.META['HTTP_HOST']+'/accounts/myaccount/basic'
        return HttpResponseRedirect(reverseStr)

    data = {'isloggedin': isloggedin, 'accountType': acType, 'advert1': adverts[0],
            'advert2': adverts[1], 'advert3': adverts[2], 'advert4': adverts[3],
            'advert5': adverts[4], 'advert6': adverts[5], 'advert7': adverts[6],
            'advert8': adverts[7], 'name': name, 'description': description,
            'deliveryTime': deliveryTime, 'categoryName': categoryName, 'stock': stock,
            'allCategories': allCategories, 'price': price, 'description': description,
            'featuresHTML': featuresHTML}

    return render(request, 'editProduct.html', data)

def add_item_page(request):
    isloggedin = False
    acType = 'none'
    if request.session.has_key('useremail'):
        isloggedin = True
        acType = accountType(request.session['useremail'])
        if acType != 'seller':
            return HttpResponseRedirect(reverse('home_page'))
    else:
        return HttpResponseRedirect(reverse('home_page'))

    adverts = getAdverts(request)

    if request.method == 'POST':
        id = request.POST.get("productID")
        id = int(id) if len(id)>0 else -1
        name = request.POST.get("productName")
        price = float(request.POST.get("productPrice"))
        deliveryTime = int(request.POST.get("deliveryTime"))
        category = request.POST.get("chosenCategory")
        description = request.POST.get("description")
        quantityInStock = int(request.POST.get("quantityInStock"))
        feature1 = request.POST.get("feature1")
        feature2 = request.POST.get("feature2")
        feature3 = request.POST.get("feature3")
        feature4 = request.POST.get("feature4")
        feature5 = request.POST.get("feature5")
        feature6 = request.POST.get("feature6")

        pics = []
        if 'productImage' in request.FILES:
            for pic in request.FILES.getlist('productImage'):
                img = Image.open(pic)
                squareImg = make_image_square(img)
                w, h = squareImg.size
                if w>640:
                    img = squareImg.resize((640, 640))
                blob = io.BytesIO()
                squareImg.save(blob, 'jpeg')
                blob.seek(0)
                pics.append(blob.getvalue())

        with connections['oracle'].cursor() as cursor:
            if len(pics) == 1:
                cursor.callproc("ADD_ITEM", [request.session['useremail'], id, name, price,
                                             deliveryTime, category, description, quantityInStock,
                                             feature1, feature2, feature3, feature4, feature5,
                                             feature6, pics[0]])
            elif len(pics) == 2:
                cursor.callproc("ADD_ITEM", [request.session['useremail'], id, name, price,
                                             deliveryTime, category, description, quantityInStock,
                                             feature1, feature2, feature3, feature4, feature5,
                                             feature6, pics[0], pics[1]])
            elif len(pics) == 3:
                cursor.callproc("ADD_ITEM", [request.session['useremail'], id, name, price,
                                             deliveryTime, category, description, quantityInStock,
                                             feature1, feature2, feature3, feature4, feature5,
                                             feature6, pics[0], pics[1], pics[2]])
            elif len(pics) == 4:
                cursor.callproc("ADD_ITEM", [request.session['useremail'], id, name, price,
                                             deliveryTime, category, description, quantityInStock,
                                             feature1, feature2, feature3, feature4, feature5,
                                             feature6, pics[0], pics[1], pics[2], pics[3]])

        reverseStr = 'http://'+request.META['HTTP_HOST']+'/accounts/myaccount/basic'
        return HttpResponseRedirect(reverseStr)

    data = {'isloggedin': isloggedin, 'accountType': acType, 'advert1': adverts[0],
            'advert2': adverts[1], 'advert3': adverts[2], 'advert4': adverts[3],
            'advert5': adverts[4], 'advert6': adverts[5], 'advert7': adverts[6],
            'advert8': adverts[7]}

    return render(request, 'newProduct.html', data)

def check_category(category):
    query = "SELECT CATEGORY_ID FROM CATEGORY WHERE CATEGORY_NAME = :category"
    with connections['oracle'].cursor() as cursor:
        cursor.execute(query , {'category' : category})
        result = cursor.fetchall()
        if(len(result) != 0):
            return True
        else:
            return False

def search_result(request, search_string):
    returnToHome = True
    for i in search_string:
        if i!='_':
            returnToHome = False
    if returnToHome:
        previous_page = request.META['HTTP_REFERER']
        return HttpResponseRedirect(previous_page)

    isloggedin = False
    acType = 'none'
    if request.session.has_key('useremail'):
        isloggedin = True
        acType = accountType(request.session['useremail'])

    adverts = getAdverts(request)

    if search_string.startswith('category_') and len(search_string)>len('category_'):
        category = search_string[len('category_'):]
        temp = ''
        for i in category.split('_'):
            if len(i)>0:
                temp += i + ' '
        category = temp[:-1]
        category = category.replace('and', '&')
        category = category.replace('Mens Fashion', 'Men\'s Fashion')
        category = category.replace('Womens Fashion', 'Women\'s Fashion')

        if(check_category(category)):
            query="""SELECT PR.PRODUCT_ID, PR.SELLER_ID,PR.NAME PRODUCT_NAME, AVG_RATING(PR.PRODUCT_ID, PR.SELLER_ID) AVG_RATE, P.PICTURE PIC1 , PP.PICTURE PIC2,
                    PR.PRICE , S.NAME SELLER_NAME , MAX_DISCOUNT(PR.PRODUCT_ID, PR.SELLER_ID) FROM
                    PRODUCT PR LEFT OUTER JOIN PRODUCT_PICTURE P ON (PR.SELLER_ID = P.SELLER_ID AND PR.PRODUCT_ID = P.PRODUCT_ID AND P.PICTURE_NUMBER = 1)
                    LEFT OUTER JOIN PRODUCT_PICTURE PP ON (PR.SELLER_ID = PP.SELLER_ID AND PR.PRODUCT_ID = PP.PRODUCT_ID AND PP.PICTURE_NUMBER = 2)
                    JOIN SELLER S ON (PR.SELLER_ID = S.SELLER_ID)
                    WHERE PR.CATEGORY_ID = (SELECT CATEGORY_ID FROM CATEGORY WHERE CATEGORY_NAME =:category)
                    AND ROWNUM <= 80"""
            products = []
            with connections['oracle'].cursor() as cursor:
                cursor.execute(query, {'category':category})
                table = cursor.fetchall()
                for i in range(len(table)):
                    temp= []
                    for j in range(len(table[i])):
                        temp.append(table[i][j])
                    if( temp[3] == None ):
                        temp[3] = 0
                    if( temp[8] == None ):
                        temp[8] = 0
                    if( temp[5] == None ):
                        temp[5] = temp[4]
                    products.append(temp)

            words = []
            for i in search_string.split('_'):
                if len(i)>0:
                    words.append(i)
            words = ' '.join(words)

            productHTML = loadProductData(request, products)
            data = {'isloggedin': isloggedin, 'accountType': acType, "productHTML": productHTML,
                    'searchString': words, 'showOffersOnly': True, 'advert1': adverts[0],
                    'advert2': adverts[1], 'advert3': adverts[2], 'advert4': adverts[3],
                    'advert5': adverts[4], 'advert6': adverts[5], 'advert7': adverts[6],
                    'advert8': adverts[7]}
            return render(request, 'search_result.html', data )

    elif search_string == 'Offers_Only':
        query =  """SELECT PR.PRODUCT_ID, PR.SELLER_ID,PR.NAME PRODUCT_NAME, AVG_RATING(PR.PRODUCT_ID, PR.SELLER_ID) AVG_RATE, P.PICTURE PIC1 , PP.PICTURE PIC2,
                    PR.PRICE , S.NAME SELLER_NAME , MAX_DISCOUNT(PR.PRODUCT_ID, PR.SELLER_ID) DISCOUNT FROM
                    PRODUCT PR JOIN SELLER S ON (PR.SELLER_ID = S.SELLER_ID) JOIN OFFER Y ON(PR.PRODUCT_ID=Y.PRODUCT_ID AND PR.SELLER_ID=Y.SELLER_ID AND
                    MAX_DISCOUNT(PR.PRODUCT_ID, PR.SELLER_ID) = Y.PERCENTAGE_DISCOUNT)
                    LEFT OUTER JOIN PRODUCT_PICTURE P ON (PR.SELLER_ID = P.SELLER_ID AND PR.PRODUCT_ID = P.PRODUCT_ID AND P.PICTURE_NUMBER = 1)
                    LEFT OUTER JOIN PRODUCT_PICTURE PP ON (PR.SELLER_ID = PP.SELLER_ID AND PR.PRODUCT_ID = PP.PRODUCT_ID AND PP.PICTURE_NUMBER = 2)
                    WHERE Y.END_DATE >= SYSDATE
                    AND ROWNUM <= 80
                    ORDER BY DISCOUNT DESC"""
        with connections['oracle'].cursor() as cursor:
            cursor.execute(query)
            table = cursor.fetchall()
            products = []
            for i in range(len(table)):
                temp= []
                for j in range(len(table[i])):
                    temp.append(table[i][j])
                if temp[3] == None:
                    temp[3] = 0
                if temp[5] == None:
                    temp[5] = temp[4]
                products.append(temp)
        productHTML = loadProductData(request, products)

        words = []
        for i in search_string.split('_'):
            if len(i)>0:
                words.append(i)
        words = ' '.join(words)

        data = {'isloggedin': isloggedin, 'accountType': acType, "productHTML": productHTML,
                'searchString': words, 'showOffersOnly': False, 'advert1': adverts[0],
                'advert2': adverts[1], 'advert3': adverts[2], 'advert4': adverts[3],
                'advert5': adverts[4], 'advert6': adverts[5], 'advert7': adverts[6],
                'advert8': adverts[7]}
        return render(request, 'search_result.html', data )

    words = []
    for i in search_string.split('_'):
        if len(i)>0:
            words.append(i)
    words = ' '.join(words)

    query =  """SELECT GREATEST(STRING_SIMILARITY(:words, PR.NAME) , STRING_SIMILARITY(:words, S.NAME)) AS MAX_SCORE ,
               PR.PRODUCT_ID, PR.SELLER_ID,PR.NAME PRODUCT_NAME, AVG_RATING(PR.PRODUCT_ID, PR.SELLER_ID) AVG_RATE,
                P.PICTURE PIC1 , PP.PICTURE PIC2, PR.PRICE , S.NAME SELLER_NAME , MAX_DISCOUNT(PR.PRODUCT_ID, PR.SELLER_ID) FROM
                PRODUCT PR LEFT OUTER JOIN PRODUCT_PICTURE P ON (PR.SELLER_ID = P.SELLER_ID AND PR.PRODUCT_ID = P.PRODUCT_ID AND P.PICTURE_NUMBER = 1)
                LEFT OUTER JOIN PRODUCT_PICTURE PP ON (PR.SELLER_ID = PP.SELLER_ID AND PR.PRODUCT_ID = PP.PRODUCT_ID AND PP.PICTURE_NUMBER = 2)
                JOIN SELLER S ON (PR.SELLER_ID = S.SELLER_ID)
                WHERE ROWNUM <= 80 AND GREATEST(STRING_SIMILARITY(:words, PR.NAME) , STRING_SIMILARITY(:words, S.NAME)) > 0
                ORDER BY MAX_SCORE DESC"""

    products = []
    with connections['oracle'].cursor() as cursor:
        cursor.execute(query, {'words':words})
        table = cursor.fetchall()
        for i in range(len(table)):
            temp = []
            for j in range(len(table[i])-1):
                temp.append(table[i][j+1])
            if( temp[3] == None ):
                temp[3] = 0
            if( temp[8] == None ):
                temp[8] = 0
            if( temp[5] == None ):
                temp[5] = temp[4]
            products.append(temp)

    productHTML = loadProductData(request, products)
    data = {'isloggedin': isloggedin, 'accountType': acType, "productHTML": productHTML,
            'searchString': words, 'showOffersOnly': True, 'advert1': adverts[0],
            'advert2': adverts[1], 'advert3': adverts[2], 'advert4': adverts[3],
            'advert5': adverts[4], 'advert6': adverts[5], 'advert7': adverts[6],
            'advert8': adverts[7]}
    return render(request, 'search_result.html', data )

def loadProductData(request, products):
    total = len(products)
    productHTML = ""
    for i in range(0, total):
        productURL = "http://{}/product/item/{}/{}/".format(request.META['HTTP_HOST'], products[i][0], products[i][1])
        productName = products[i][2]
        if len(productName) > 24:
            productName = productName[:21] + "..."
        productPrice = products[i][6]
        productDiscount = products[i][8]
        sellerName = products[i][7]
        if len(sellerName) >= 20:
            sellerName = sellerName[:18] + "..."
        ratingHTML = ""

        rating = float(products[i][3])
        temp = rating
        ratingHTML = ""
        starCount = 0
        while temp>=1:
            ratingHTML += '<i class="star fa fa-star text-warning"></i>'
            temp -= 1
            starCount += 1
        if temp>0 and temp<1:
            ratingHTML += '<i class="fa fa-star-half-o text-warning" aria-hidden="true"></i>'
            starCount += 1
        while starCount < 5:
            ratingHTML += '<i class="fa fa-star-o text-warning" aria-hidden="true"></i>'
            starCount += 1

        image1Path = "http://{}/static/images/productImages/{}_{}_1.jpg".format(request.META['HTTP_HOST'], products[i][0], products[i][1])
        image2Path = "http://{}/static/images/productImages/{}_{}_2.jpg".format(request.META['HTTP_HOST'], products[i][0], products[i][1])

        reviewCount = 0
        with connections['oracle'].cursor() as cursor:
            query = "SELECT COUNT(*) FROM REVIEW WHERE PRODUCT_ID = :product_id AND SELLER_ID = :seller_id"
            cursor.execute(query, {'product_id': products[i][0], 'seller_id': products[i][1]})
            reviewCount = int( cursor.fetchall()[0][0] )

        inStock = 0
        with connections['oracle'].cursor() as cursor:
            query = """SELECT COUNT(*) FROM PRODUCT_UNIT WHERE PRODUCT_ID = :product_id AND
                       SELLER_ID = :seller_id AND LOWER(STATUS) = 'not sold'"""
            cursor.execute(query, {'product_id': products[i][0], 'seller_id': products[i][1]})
            inStock = int( cursor.fetchall()[0][0] )

        productHTML += htmlGenerator(i, productURL, productName, productPrice, productDiscount, sellerName, ratingHTML, image1Path, image2Path, starCount, rating, reviewCount, inStock)

        imageFile1 = open(settings.BASE_DIR+"\\static\\images\\productImages\\{}_{}_1.jpg".format(products[i][0], products[i][1]),'wb')
        imageFile2 = open(settings.BASE_DIR+"\\static\\images\\productImages\\{}_{}_2.jpg".format(products[i][0], products[i][1]),'wb')

        imageFile1.write( products[i][4].read() )
        imageFile2.write( products[i][5].read() )

        imageFile1.close()
        imageFile2.close()

    return productHTML

def htmlGenerator(i, productURL, productName, productPrice, productDiscount, sellerName, ratingHTML, image1Path, image2Path, starCount, rating, reviewCount, inStock):
    hasOffer = "no"
    if float(productDiscount)>0:
        hasOffer = "yes"
    reviewText = 'reviews'
    if reviewCount == 1:
        reviewText = 'review'
    stockIcon = '<i style="margin-left: 20px" class="text-danger fa fa-times-circle" aria-hidden="true"></i>'
    discountIcon = '<i style="margin-left: 20px" class="text-danger fa fa-times-circle" aria-hidden="true"></i>'
    if productDiscount is None:
        productDiscount = 0
    productDiscount = int(productDiscount)
    if( productDiscount > 0 ):
        discountIcon = '<i style="margin-left: 20px" class="text-success fa fa-check-circle" aria-hidden="true"></i>'
    if( inStock > 0 ):
        stockIcon = '<i style="margin-left: 20px" class="text-success fa fa-check-circle" aria-hidden="true"></i>'
    return """<div class="productItems col-md-6 col-lg-3" id="product{}" style="display: none;">
                <label class="searchRank" style="display:none">{}</label>
                <label class="productRatings" style="display:none">{}</label>
                <label class="hasOffer" style="display:none">{}</label>
                <div class="card shadow border-light mb-4" style="background-color: #f2f8f8">
                <div class="product-grid7" style="padding: 0.5px; background-color: rgba(31, 171, 136, 0.1);">
                <div class="product-image7">
                    <a href="{}">
                        <img class="pic-1" src="{}">
                        <img class="pic-2" src="{}">
                    </a>
                </div>
                </div>
                        <div style="padding: 10px; padding-top:5px;" class="card-body">
                            <a href="{}">
                                <p style="margin:0px; padding:0px" class="font-weight-normal">{}</p>
                            </a>
                            <div class="post-meta"><span class="small lh-120"><i class="fa fa-building" aria-hidden="true"></i> <span class="sellerName">{}</span></span></div>
                            <div style="padding-top: 5px; padding-bottom: 5px">
                                {} <span class="badge badge-pill badge-secondary ml-2">{}</span>
                  <small class="text-info" style="font-size: 10px">&nbsp;{} {} </small>
                </div>
                            <div class="d-flex justify-content-between" style="padding-top: 0px">
                                <div class="col pl-0" style="padding: 1px">
                    <span class="text-muted font-small d-block">Price</span>
                    <span class="text-dark font-weight-bold">
                      <span style="font-size: 13px"><strong>৳</strong><span class="productPrices">{}</span></span>
                    </span>
                  </div>
                                <div class="col" style="padding: 1px">
                    <span class="text-muted font-small d-block">In Stock</span>
                    {}
                  </div>
                                <div class="col pr-0" style="padding: 1px">
                    <span class="text-muted font-small d-block">Discount</span>
                    {}
                  </div>
                            </div>
                        </div>
                    </div>
                </div>""".format(i, i, rating, hasOffer, productURL, image1Path, image2Path, productURL, productName, sellerName, ratingHTML, rating, reviewCount, reviewText, productPrice, stockIcon, discountIcon) + "\n"

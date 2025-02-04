import json
import paho.mqtt.client as mqtt
from django.shortcuts import render
from django.http import JsonResponse
import datetime
from .models import *
# from django.db import connection
# from django.db import Q
from .utils import cookieCart, cartData, guestOrder
from django.contrib.auth.decorators import login_required

# Create your views here.
def login(request):
    #return render(request, 'users/login.html')
	pass

@login_required
def store(request):
	data = cartData(request)
	cartItems = data['cartItems']
	order = data['order']

	products = Product.objects.all()
	context = {'products':products, 'cartItems':cartItems}
	return render(request, 'store/store.html', context)

@login_required
def delivery(request):
	# mqttSub()
	# orders = Order.objects.all()
	orders = Order.objects.filter(complete=True) & Order.objects.filter(deliveried=False)
	# orders = Order.objects.filter(Q(complete=True) & Q(deliveried=False))

	context = {'orders':orders}
	return render(request, 'store/delivery.html', context)

def mqttSub():
	pass

def cart(request):
	data = cartData(request)

	cartItems = data['cartItems']
	order = data['order']
	items = data['items']

	context = {'items':items, 'order':order, 'cartItems':cartItems}
	return render(request, 'store/cart.html', context)
	
def checkout(request):
	data = cartData(request)

	cartItems = data['cartItems']
	order = data['order']
	items = data['items']

	context = {'items':items, 'order':order, 'cartItems':cartItems}
	return render(request, 'store/checkout.html', context)
	
def updateItem(request):
	data = json.loads(request.body)
	productId = data['productId']
	action = data['action']
	print('Action:', action)
	print('Product:', productId)

	customer = request.user.customer
	product = Product.objects.get(id=productId)
	order, created = Order.objects.get_or_create(customer=customer, complete=False)

	orderItem, created = OrderItem.objects.get_or_create(order=order, product=product)

	if action == 'add':
		orderItem.quantity = (orderItem.quantity + 1)
	elif action == 'remove':
		orderItem.quantity = (orderItem.quantity - 1)

	orderItem.save()

	if orderItem.quantity <= 0:
		orderItem.delete()

	return JsonResponse('Item was added', safe=False)

def processOrder(request):
	transaction_id = datetime.datetime.now().timestamp()
	data = json.loads(request.body)
	if request.user.is_authenticated:
		customer = request.user.customer
		order, created = Order.objects.get_or_create(customer=customer, complete=False)
	else:
		customer, order = guestOrder(request, data)

	total = float(data['form']['total'])
	track = data['form']['track']
	position = data['form']['position']

	order.transaction_id = transaction_id
	order.track = track
	order.position = position

	if total == order.get_cart_total:
		order.complete = True
	order.save()

	if order.shipping == True:
		ShippingAddress.objects.create(
		customer=customer,
		order=order,
		address=data['shipping']['address'],
		city=data['shipping']['city'],
		state=data['shipping']['state'],
		zipcode=data['shipping']['zipcode'],
		)

	return JsonResponse('Payment complete', safe=False)

def deliveryCart(request):
	data = json.loads(request.body)

	orderID = data['orderID']
	order = Order.objects.get(id=orderID)
	orderTrack = order.track
	orderPosition = order.position

	print('Track:', orderTrack)
	print('Position:', orderPosition)
	"""
	train_cmd = {
		"Track": orderTrack,
		"Position":orderPosition
	}
	"""

	train_cmd = {
		"traffic": {"travel": orderPosition} # '01' ~ '05'
	}
	payload = json.dumps(train_cmd) # encode dict oject to JSON

	def connect_msg():
		print('Connect to Broker')


	def publish_msg():
		print('Message Published')


	client = mqtt.Client(client_id='publish-cherpa') # publisher cherpa
	client.on_connect = connect_msg()
	client.on_publish = publish_msg()
	client.username_pw_set(username='pub_client', password='password')
	client.connect('127.0.0.1', 1883, 60)
	# client.connect('192.168.50.172', 1883)
	# client.connect('192.168.168.57', 1883)  # 我的手機 ip
	# client.connect('192.168.0.200', 1883) # 競賽 IP
	
	# publish to mqtt
	if orderTrack == 'A1':
		# 電車 A1 出發前往餐桌
		print('電車 A1 出發前往餐桌： ', orderPosition )
		ret = client.publish('tram/v1/cherpa/A1/tell', payload)
	else:
		print('電車 A2 出發前往餐桌： ', orderPosition )
		ret = client.publish('tram/v1/cherpa/A2/tell', payload)

	# ret = client.publish('train/v1/go', payload) # tram/v1/cherpa/A1/tell 
	# (subscribe: tram/v1/cherpa/A1/listen)

	client.loop()
	if ret[0] == 0:
		order.deliveried = True
		order.save()
	else:
		print(f"Failed to send message, return code:", ret[0])

	client.disconnect()
	return JsonResponse('Delivery Complete', safe=False)

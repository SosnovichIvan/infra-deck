import re
from concurrent.futures import ThreadPoolExecutor

import pytest

from conftest import PASSWORD
from infradeck.crypto import token_hash
from infradeck.errors import Rejected
from infradeck.schemas import Login


def otp(browser,telegram):
    response=browser.register()
    browser.bind(response.json()['telegram_url'])
    response=browser.call('POST','/auth/send-code')
    assert response.status_code==200,response.text
    return re.search(r'\b\d{8}\b',telegram.send.call_args.args[1])[0]


def test_register_bind_otp_logout(browser,telegram,db):
    code=otp(browser,telegram)
    assert browser.call('GET','/projects').status_code==401
    before=browser.client.cookies.get('session')
    response=browser.call('POST','/auth/verify',{'code':code})
    assert response.status_code==200
    assert len(response.json()['recovery_codes'])==8
    assert before!=browser.client.cookies.get('session')
    assert browser.call('GET','/auth/me').json()['login']=='tester'
    assert browser.call('GET','/projects').json()==[]
    with db.transaction() as tx:
        row=tx.execute('SELECT * FROM users').fetchone()
        assert row['password_hash'].startswith('$argon2id$')
        assert PASSWORD not in str(row)
        assert code not in str(tx.execute('SELECT * FROM sessions').fetchall())
    assert browser.call('POST','/auth/logout').status_code==204
    assert browser.call('GET','/auth/me').status_code==401


def test_register_validation_duplicate(browser):
    assert browser.call('POST','/auth/register',{'login':'abc','password':PASSWORD,
        'confirmation':'wrongpassword123'}).status_code==400
    assert browser.register().status_code==200
    assert browser.register().status_code==409
    bad=browser.call('POST','/auth/register',{'login':'!','password':'private-value',
        'confirmation':'private-value'})
    assert bad.status_code==422 and 'private-value' not in bad.text


@pytest.mark.parametrize('login,password',[('missing',PASSWORD),('tester','Wrong-password-123')])
def test_bad_credentials(browser,login,password):
    browser.register()
    response=browser.call('POST','/auth/login',{'login':login,'password':password})
    assert response.status_code==401
    assert response.json()['detail']=='Неверный логин или пароль'


def test_before_binding_and_replay_update(browser,telegram):
    response=browser.register()
    link=response.json()['telegram_url']
    assert browser.call('POST','/auth/send-code').status_code==409
    assert browser.bind(link).status_code==200
    assert browser.bind(link).status_code==200
    assert telegram.send.call_count==1
    assert browser.bind('https://t.me/bot?start=not-valid',update=2).status_code==200
    assert telegram.send.call_count==1


def test_wrong_expired_attempts_and_resend(browser,telegram,db):
    code=otp(browser,telegram)
    assert browser.call('POST','/auth/send-code').status_code==429
    assert browser.call('POST','/auth/verify',{'code':'00000000' if code!='00000000' else '11111111'}).status_code==401
    with db.transaction() as tx:
        tx.execute('UPDATE sessions SET otp_expires=0,last_sent=0')
    assert browser.call('POST','/auth/verify',{'code':code}).status_code==401
    assert browser.call('POST','/auth/send-code').status_code==200
    with db.transaction() as tx:
        assert tx.execute('SELECT attempts FROM sessions').fetchone()['attempts']==2
    for _ in range(3):
        assert browser.call('POST','/auth/verify',{'code':'bad'}).status_code==422
        assert browser.call('POST','/auth/verify',{'code':'99999999'}).status_code==401
    with db.transaction() as tx:
        tx.execute('UPDATE sessions SET last_sent=0')
    assert browser.call('POST','/auth/send-code').status_code==429


def test_delivery_failure_does_not_start_countdown(browser,telegram,db):
    response=browser.register();browser.bind(response.json()['telegram_url'])
    telegram.send.side_effect=Rejected('Telegram недоступен',503)
    response=browser.call('POST','/auth/send-code')
    assert response.status_code==503 and 'expires_at' not in response.json()
    with db.transaction() as tx:
        assert tx.execute('SELECT otp_digest FROM sessions').fetchone()['otp_digest'] is None


def test_single_use_concurrent(browser,telegram,auth):
    code=otp(browser,telegram);token=browser.client.cookies.get('session')
    def verify():
        try:return auth.verify(token,code)[1].state
        except Rejected:return 'rejected'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _:verify(),range(2)))==['authenticated','rejected']


def test_recovery_single_use(logged,auth,telegram,db):
    # Issue fresh recovery codes through a new OTP (existing hashes are never disclosed again).
    with db.transaction() as tx:
        uid=tx.execute('SELECT id FROM users').fetchone()['id']
        tx.execute('DELETE FROM recovery_codes')
    token,state=auth.login(Login(login='tester',password=PASSWORD),'other')
    auth.send_code(token)
    code=re.search(r'\b\d{8}\b',telegram.send.call_args.args[1])[0]
    full,state=auth.verify(token,code)
    recovery=state.recovery_codes[0]
    token,_=auth.login(Login(login='tester',password=PASSWORD),'another')
    full,state=auth.verify(token,recovery,True)
    assert state.state=='authenticated' and not state.recovery_codes
    token,_=auth.login(Login(login='tester',password=PASSWORD),'third')
    with pytest.raises(Rejected):auth.verify(token,recovery,True)
    assert auth.session(full)['user_id']==uid


def test_session_expiry_login_invalidates_pending(browser,auth,db):
    response=browser.register();old=browser.client.cookies.get('session')
    result=browser.call('POST','/auth/login',{'login':'tester','password':PASSWORD})
    assert result.json()['state']=='enrollment'
    with pytest.raises(Rejected):auth.session(old,('enrollment',))
    with db.transaction() as tx:tx.execute('UPDATE sessions SET expires_at=0')
    assert browser.call('GET','/auth/me').status_code==401


def test_rate_limit_and_csrf(browser,auth):
    for _ in range(5):auth.limit('limited',5)
    with pytest.raises(Rejected):auth.limit('limited',5)
    response=browser.client.post('/api/auth/login',json={'login':'tester','password':PASSWORD})
    assert response.status_code==403
    browser.client.get('/api/auth/csrf')
    response=browser.client.post('/api/auth/login',headers={'Origin':'https://evil.example',
        'X-CSRF-Token':browser.client.cookies.get('csrf')},json={})
    assert response.status_code==403


def test_telegram_permissions_and_unique(browser,auth,db):
    result=browser.register();link=result.json()['telegram_url']
    assert browser.bind(link).status_code==200
    with pytest.raises(Rejected):auth.bind_telegram(3,100,101,'token')
    with pytest.raises(Rejected):auth.bind_telegram(3,-1,-1,'token')
    result=browser.register('otheruser')
    assert browser.bind(result.json()['telegram_url'],update=4).status_code==409
    assert browser.client.post('/api/telegram/webhook',json={}).status_code==403
    assert browser.client.post('/api/telegram/webhook',headers={
        'X-Telegram-Bot-Api-Secret-Token':'s'*32},json={}).status_code==400
